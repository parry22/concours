"""IntakeAgent: one chat turn in, one IntakeResponse out. LLM first, cache second, deterministic defaults last."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app import config, llm
from app.intake.cache import IntakeCache, cache_key, fallback_reply
from app.intake.metric_policy import decide_metric, spec_is_complete
from app.intake.prompts import MAX_QUESTIONS, RESPONSE_SCHEMA, build_system_prompt
from app.value.params import normalize_economics
from app.models import DataProfile, IntakeMessage, IntakeResponse, ProblemSpec, SpecPatch
from app.templates import load_defaults, spec_from_defaults

log = logging.getLogger(__name__)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_reply(text: str) -> tuple[str, dict[str, Any], bool]:
    """Robust parse of {"message", "spec_patch", "done"}. Bad JSON becomes a plain message with an empty patch."""
    candidates = [text]
    m = _JSON_BLOCK.search(text)
    if m:
        candidates.append(m.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        message = data.get("message")
        patch = data.get("spec_patch")
        done = data.get("done")
        return (
            message if isinstance(message, str) else text,
            patch if isinstance(patch, dict) else {},
            bool(done) if isinstance(done, bool) else False,
        )
    return text.strip(), {}, False


def validate_patch(raw: dict[str, Any]) -> SpecPatch:
    """Drop null fields and anything that fails SpecPatch validation, one field at a time."""
    clean = {k: v for k, v in raw.items() if v is not None and k in SpecPatch.model_fields}
    if "metric_params" in clean and isinstance(clean["metric_params"], dict):
        clean["metric_params"] = {k: v for k, v in clean["metric_params"].items() if v is not None}
        if not clean["metric_params"]:
            del clean["metric_params"]
    if "economics" in clean and isinstance(clean["economics"], dict):
        clean["economics"] = {k: v for k, v in clean["economics"].items() if v is not None}
        if not clean["economics"]:
            del clean["economics"]
    try:
        return SpecPatch.model_validate(clean)
    except ValidationError:
        good: dict[str, Any] = {}
        for k, v in clean.items():
            try:
                SpecPatch.model_validate({k: v})
                good[k] = v
            except ValidationError:
                log.warning("intake: dropped invalid patch field %s=%r", k, v)
        return SpecPatch.model_validate(good)


def merge_economics(existing: dict[str, Any] | None, patch: dict[str, Any] | None, defaults: dict[str, Any] | None) -> dict[str, Any] | None:
    """User-given numbers only. Defaults are not copied in: the value model fills gaps from the data or labeled
    placeholders, so a number the user never gave is never shown as theirs."""
    template = (defaults or {}).get("business_template", "custom")
    merged = normalize_economics(existing, template)
    merged.update(normalize_economics(patch, template))
    return merged or None


def apply_patch(spec: ProblemSpec | None, patch: SpecPatch, *, template: str, defaults: dict[str, Any] | None) -> ProblemSpec | None:
    fields = patch.model_dump(exclude_none=True)
    econ_patch = fields.pop("economics", None)
    if spec is None:
        if not fields.get("target_column"):
            return None
        fields.setdefault("template", template)
        spec = ProblemSpec(**fields)
    else:
        fields.pop("template", None)
        if "metric_params" in fields:
            fields["metric_params"] = {**spec.metric_params, **fields["metric_params"]}
        spec = spec.model_copy(update=fields)
    econ = merge_economics(spec.economics, econ_patch, defaults)
    return spec.model_copy(update={"economics": econ}) if econ != spec.economics else spec


class IntakeAgent:
    """One instance per process. `client` is an anthropic.AsyncAnthropic or a test double with the same shape."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        model: str | None = None,
        offline: bool | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.model = model or config.INTAKE_MODEL
        self.offline = config.OFFLINE if offline is None else offline
        self.cache_root = cache_root
        self._client = client

    @property
    def client(self) -> Any | None:
        if self._client is None and not self.offline and config.ANTHROPIC_API_KEY:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
        return self._client

    @property
    def provider(self) -> str:
        if self._client is not None:
            return "api"
        return llm.provider()

    async def turn(
        self,
        *,
        template: str,
        profile: DataProfile,
        spec: ProblemSpec | None,
        history: list[IntakeMessage],
        user_message: str,
    ) -> IntakeResponse:
        defaults = load_defaults(template)
        if spec is None and defaults:
            spec = spec_from_defaults(template)
        turn_index = sum(1 for m in history if m.role == "assistant")
        cache = IntakeCache(template, self.cache_root)
        key = cache_key(template, turn_index, user_message)

        message: str | None = None
        raw_patch: dict[str, Any] = {}
        done_flag = False
        source: str = "defaults"

        client = self.client
        if not self.offline and (client is not None or self.provider == "cli"):
            try:
                message, raw_patch, done_flag = await self._call_llm(
                    client, template=template, profile=profile, defaults=defaults, spec=spec, history=history, user_message=user_message, turn_index=turn_index
                )
                source = "llm"
                cache.put(key, message=message, spec_patch=raw_patch, done=done_flag, user_text=user_message)
            except Exception as exc:  # noqa: BLE001 - any API failure falls back to cache/defaults
                log.warning("intake: live call failed, falling back: %s", exc)
                message = None

        if message is None:
            entry = cache.get(key)
            if entry:
                message, raw_patch, done_flag = str(entry.get("message", "")), dict(entry.get("spec_patch") or {}), bool(entry.get("done"))
                source = "cache"
            else:
                message, raw_patch, done_flag = fallback_reply(
                    template=template, turn_index=turn_index, profile=profile, spec=spec, defaults=defaults, user_message=user_message
                )
                source = "defaults"

        patch = validate_patch(raw_patch)
        spec = apply_patch(spec, patch, template=template, defaults=defaults)
        if spec is not None:
            spec = decide_metric(profile, spec)

        complete = spec_is_complete(spec)
        out_of_questions = turn_index + 1 >= MAX_QUESTIONS
        done = complete and (done_flag or out_of_questions)

        new_history = [*history, IntakeMessage(role="user", content=user_message), IntakeMessage(role="assistant", content=message)]
        return IntakeResponse(message=message, spec_patch=patch, spec=spec, done=done, source=source, history=new_history)  # type: ignore[arg-type]

    async def _call_llm(
        self,
        client: Any,
        *,
        template: str,
        profile: DataProfile,
        defaults: dict[str, Any] | None,
        spec: ProblemSpec | None,
        history: list[IntakeMessage],
        user_message: str,
        turn_index: int,
    ) -> tuple[str, dict[str, Any], bool]:
        system = build_system_prompt(template=template, profile=profile, defaults=defaults, spec=spec, questions_asked=turn_index)
        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": user_message})
        if client is not None:
            text = await llm.complete_api(client, system, messages, model=self.model, schema=RESPONSE_SCHEMA)
        else:
            text = await llm.complete_cli(system, messages, model=self.model)
        return parse_reply(text)
