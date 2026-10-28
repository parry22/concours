"""Cache-first replay of intake replies, plus a deterministic fallback that completes the spec from defaults.json."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.config import TEMPLATES_DIR
from app.models import DataProfile, ProblemSpec

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    t = _PUNCT.sub(" ", text.lower())
    return _WS.sub(" ", t).strip()


def cache_key(template: str, turn_index: int, user_text: str) -> str:
    raw = f"{template}\x00{turn_index}\x00{normalize_text(user_text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class IntakeCache:
    """JSON file at data/templates/<template>/intake_cache.json: key -> {message, spec_patch, done, user_text}."""

    def __init__(self, template: str, root: Path | None = None) -> None:
        self.template = template
        self.path = (root or TEMPLATES_DIR) / template / "intake_cache.json"
        self._data: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._data is None:
            try:
                self._data = json.loads(self.path.read_text()) if self.path.exists() else {}
            except (OSError, ValueError):
                self._data = {}
        return self._data

    def get(self, key: str) -> dict[str, Any] | None:
        return self._load().get(key)

    def put(self, key: str, *, message: str, spec_patch: dict[str, Any], done: bool, user_text: str) -> None:
        data = self._load()
        data[key] = {"message": message, "spec_patch": spec_patch, "done": done, "user_text": user_text}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))

    def __len__(self) -> int:
        return len(self._load())


# ---------- deterministic fallback ----------

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    out = []
    for m in _NUM.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return out


def parse_fpr(text: str) -> float | None:
    """Reads '1 in 1000', '0.1%', '0.001', '2 per 1,000' as a false-alarm fraction. None if nothing found."""
    t = text.lower()
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:in|per|out of)\s*(\d[\d,]*)", t)
    if m:
        a, b = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        return a / b if b else None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", t)
    if m:
        return float(m.group(1)) / 100
    nums = _numbers(t)
    if len(nums) == 1 and 0 < nums[0] < 1:
        return nums[0]
    return None


def parse_costs(text: str) -> tuple[float, float] | None:
    """Two money-like numbers: first is the missed positive, second the false alarm."""
    nums = [n for n in _numbers(text) if n >= 0]
    if len(nums) >= 2:
        return nums[0], nums[1]
    return None


def _column_named(profile: DataProfile, text: str) -> str | None:
    names = [c.name for c in profile.columns]
    exact = {n.lower(): n for n in names}
    for tok in re.findall(r"[\w\s]+", text):
        if tok.strip().lower() in exact:
            return exact[tok.strip().lower()]
    norm = normalize_text(text)
    for n in sorted(names, key=len, reverse=True):
        if normalize_text(n) and normalize_text(n) in norm:
            return n
    return None


def _positive_label_guess(profile: DataProfile, column: str) -> str | int | None:
    vals = [r.get(column) for r in profile.sample_rows if r.get(column) is not None]
    if not vals:
        return None
    as_str = {str(v) for v in vals}
    if as_str <= {"0", "1", "True", "False", "true", "false"}:
        return 1
    if len(as_str) == 2:
        counts = {s: sum(1 for v in vals if str(v) == s) for s in as_str}
        return min(counts, key=counts.get)
    return None


def fallback_reply(
    *,
    template: str,
    turn_index: int,
    profile: DataProfile,
    spec: ProblemSpec | None,
    defaults: dict[str, Any] | None,
    user_message: str,
) -> tuple[str, dict[str, Any], bool]:
    """Deterministic reply when no LLM and no cached entry. Returns (message, spec_patch, done)."""
    if defaults:
        return _fallback_with_defaults(turn_index, defaults, user_message)
    return _fallback_custom(profile, spec, user_message)


def _fallback_with_defaults(turn_index: int, defaults: dict[str, Any], user_message: str) -> tuple[str, dict[str, Any], bool]:
    target = defaults["target_column"]
    label = defaults.get("positive_label")
    time_col = defaults.get("time_column")
    metric = defaults.get("primary_metric", "recall_at_fpr")
    params = dict(defaults.get("metric_params") or {})
    econ = defaults.get("economics_defaults") or {}
    rare = metric == "recall_at_fpr"

    if turn_index == 0:
        patch: dict[str, Any] = {
            "target_column": target,
            "positive_label": label,
            "time_column": time_col,
            "primary_metric": metric,
            "metric_params": params,
        }
        if rare:
            msg = (
                f"Thanks. I will use the {target} column as the outcome, where {label} means a confirmed case. "
                "How many false alarms are acceptable? For example, 1 in 1,000 good transactions."
            )
        else:
            msg = (
                f"Thanks. I will use the {target} column as the outcome, where {label} means the customer left. "
                "What share of customers can your team contact each month? For example, the riskiest 10%."
            )
        return msg, patch, False

    if turn_index == 1:
        patch = {}
        if rare:
            fpr = parse_fpr(user_message)
            if fpr is not None:
                patch["metric_params"] = {"fpr": fpr}
            msg = "Got it. Roughly, what does a missed case cost you, and what does a false alarm cost? Two numbers are enough."
        else:
            fpr = parse_fpr(user_message)
            if fpr is not None:
                patch["metric_params"] = {"top_k": fpr}
            msg = "Got it. Roughly, what does a lost customer cost you, and what does one contact cost? Two numbers are enough."
        return msg, patch, False

    patch = {}
    costs = parse_costs(user_message)
    if costs:
        patch["economics"] = {"monthly_volume": econ.get("monthly_volume"), "cost_fn": costs[0], "cost_fp": costs[1]}
    elif econ:
        patch["economics"] = dict(econ)
    msg = "Thanks. The problem is set up. You can review and change any detail before protecting the data."
    return msg, patch, True


def _fallback_custom(profile: DataProfile, spec: ProblemSpec | None, user_message: str) -> tuple[str, dict[str, Any], bool]:
    if spec is not None and spec.target_column and spec.positive_label is not None:
        return "Thanks. The problem is set up. You can review and change any detail before protecting the data.", {}, True
    if spec is not None and spec.target_column and spec.positive_label is None:
        # We already asked which value means yes; take the first word of the answer.
        words = user_message.strip().split()
        if words:
            raw = words[0].strip("\"'.,")
            label: str | int = int(raw) if raw.lstrip("-").isdigit() else raw
            return "Thanks. The problem is set up. You can review and change any detail before protecting the data.", {"positive_label": label}, True

    col = _column_named(profile, user_message)
    if col is None:
        cands = profile.target_candidates[:3]
        hint = f" Likely options: {', '.join(cands)}." if cands else ""
        return (
            f"Which column holds the outcome you want to predict? Please name it exactly as it appears in the file.{hint}",
            {},
            False,
        )

    patch: dict[str, Any] = {"target_column": col}
    label = _positive_label_guess(profile, col)
    if label is not None:
        patch["positive_label"] = label
        time_col = next((c.name for c in profile.columns if c.looks_like_time), None)
        if time_col:
            patch["time_column"] = time_col
        return f"Thanks. I will use the {col} column as the outcome, where {label} means a confirmed case. The problem is set up.", patch, True
    return f"Thanks. I will use the {col} column as the outcome. Which value in it means yes?", patch, False
