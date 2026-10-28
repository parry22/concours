"""One LLM entry point for Brief. Two providers, picked at runtime:

- "api": the Anthropic Messages API when ANTHROPIC_API_KEY is set.
- "cli": the installed Claude Code CLI (`claude -p`), which runs on the user's Claude subscription.
  Used for the demo when no API key is set. Needs `claude auth login` once in a terminal.

Both return the model's text for a (system, messages) pair. Structured output is requested by
instruction and parsed by the caller; the CLI path cannot enforce a JSON schema.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any

from app import config

# Env vars that mark "running inside Claude Code"; a nested `claude -p` refuses to start with them set.
_STRIP_ENV_PREFIXES = ("CLAUDECODE", "CLAUDE_CODE_", "CLAUDE_AGENT_SDK", "CLAUDE_PID", "CLAUDE_EFFORT", "CLAUDE_PREVIEW")


def cli_path() -> str | None:
    return shutil.which("claude") or (os.path.expanduser("~/.local/bin/claude") if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else None)


def provider() -> str:
    if config.ANTHROPIC_API_KEY:
        return "api"
    if cli_path() and not config.OFFLINE_FORCED:
        return "cli"
    return "none"


def _cli_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(_STRIP_ENV_PREFIXES)}


async def cli_logged_in() -> bool:
    exe = cli_path()
    if not exe:
        return False
    try:
        proc = await asyncio.create_subprocess_exec(exe, "auth", "status", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_cli_env())
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return bool(json.loads(out.decode() or "{}").get("loggedIn"))
    except (OSError, ValueError, asyncio.TimeoutError):
        return False


def _render_transcript(messages: list[dict[str, str]]) -> str:
    """The CLI takes one prompt, so earlier turns are rendered into it verbatim."""
    lines = []
    for m in messages[:-1]:
        who = "Business lead" if m["role"] == "user" else "You (intake analyst)"
        lines.append(f"{who}: {m['content']}")
    last = messages[-1]["content"]
    if lines:
        return "Conversation so far:\n" + "\n".join(lines) + f"\n\nBusiness lead: {last}\n\nReply now, JSON only."
    return f"Business lead: {last}\n\nReply now, JSON only."


async def complete_cli(system: str, messages: list[dict[str, str]], *, model: str, timeout_s: float = 120) -> str:
    exe = cli_path()
    if not exe:
        raise RuntimeError("claude CLI not found")
    args = [exe, "-p", _render_transcript(messages), "--output-format", "json", "--model", model,
            "--system-prompt", system, "--tools", "", "--no-session-persistence"]
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=_cli_env(), cwd=str(config.WORKSPACE_DIR))
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("claude CLI timed out") from None
    text = out.decode(errors="replace").strip()
    try:
        data = json.loads(text)
    except ValueError:
        raise RuntimeError(f"claude CLI returned non-JSON: {text[:200]} {err.decode(errors='replace')[:200]}") from None
    if data.get("is_error"):
        raise RuntimeError(f"claude CLI error: {data.get('result')}")
    result = data.get("result")
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError("claude CLI returned an empty result")
    return result


async def complete_api(client: Any, system: str, messages: list[dict[str, str]], *, model: str, schema: dict | None = None) -> str:
    kwargs: dict[str, Any] = {}
    if schema:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}, "effort": "low"}
    response = await client.messages.create(model=model, max_tokens=2048, system=system, messages=messages, **kwargs)
    if getattr(response, "stop_reason", None) == "refusal":
        raise RuntimeError("model declined the request")
    text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", None) == "text")
    if not text.strip():
        raise RuntimeError("empty reply")
    return text
