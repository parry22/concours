"""Prompt text for the intake agent. The LLM sees the data profile and masked sample rows, never raw data."""
from __future__ import annotations

import json
from typing import Any

from app.models import DataProfile, ProblemSpec

SYSTEM_PROMPT = """You are Concours's intake analyst. You help a non-technical business lead turn a goal into a measurable prediction problem.
You see a data profile and masked sample rows, never full data.
Ask at most three short questions, one at a time, in plain business language. Never use ML jargon unless the user does.
Propose: target column, positive label, acceptable false alarms, time column, constraints.
Return only JSON: {"message": str, "spec_patch": object, "done": bool}.
If a column looks like it records something that happens after the outcome (refunds, chargebacks, dispute status), mention it as a possible leak.

Rules for spec_patch:
- Only include fields you are confident about. Leave the rest null.
- metric_params uses {"fpr": <fraction>} for rare outcomes or {"top_k": <fraction>} for common ones. A false alarm rate of 1 per 1,000 is {"fpr": 0.001}.
- economics uses {"rows_per_month": <rows scored per month>, "value_per_positive": <money at stake per positive, e.g. the fraud amount or the revenue a saved customer keeps>, "action_success_rate": <share of flagged positives where acting works, 0 to 1>, "cost_per_action": <cost to act on one flagged row>, "cost_per_false_positive": <extra cost of a wrong flag>}. Only fill it from numbers the user gave; the app measures the rest from the data.
- When template defaults are shown, confirm them in your first message instead of asking from scratch.
- Never write numbers about the data into the message. The app computes and shows every number.
- Set done to true once the checklist below is complete. Short sentences. No em dashes. No exclamation marks."""

REQUIRED_FIELDS = ("target_column", "positive_label", "metric_params")

MAX_QUESTIONS = 3

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {"type": "string"},
        "spec_patch": {
            "type": "object",
            "properties": {
                "target_column": {"type": ["string", "null"]},
                "positive_label": {"type": ["string", "integer", "null"]},
                "time_column": {"type": ["string", "null"]},
                "task_type": {"type": ["string", "null"], "enum": ["binary", "regression", None]},
                "primary_metric": {"type": ["string", "null"], "enum": ["recall_at_fpr", "recall_at_top_k", "wape", None]},
                "metric_params": {
                    "type": ["object", "null"],
                    "properties": {"fpr": {"type": ["number", "null"]}, "top_k": {"type": ["number", "null"]}},
                    "required": ["fpr", "top_k"],
                    "additionalProperties": False,
                },
                "economics": {
                    "type": ["object", "null"],
                    "properties": {
                        "rows_per_month": {"type": ["number", "null"]},
                        "value_per_positive": {"type": ["number", "null"]},
                        "action_success_rate": {"type": ["number", "null"]},
                        "cost_per_action": {"type": ["number", "null"]},
                        "cost_per_false_positive": {"type": ["number", "null"]},
                    },
                    "required": ["rows_per_month", "value_per_positive", "action_success_rate", "cost_per_action", "cost_per_false_positive"],
                    "additionalProperties": False,
                },
            },
            "required": ["target_column", "positive_label", "time_column", "task_type", "primary_metric", "metric_params", "economics"],
            "additionalProperties": False,
        },
        "done": {"type": "boolean"},
    },
    "required": ["message", "spec_patch", "done"],
    "additionalProperties": False,
}


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def render_profile(profile: DataProfile) -> str:
    lines = [f"Rows: {profile.n_rows:,}. Columns: {profile.n_cols}."]
    if profile.positive_rate is not None:
        lines.append(f"Positive rate of the likely target: {profile.positive_rate:.4f}.")
    if profile.target_candidates:
        lines.append("Likely target columns: " + ", ".join(profile.target_candidates) + ".")
    lines.append("name | dtype | null % | unique ratio | min | max | looks like time")
    for c in profile.columns:
        lines.append(
            f"{c.name} | {c.dtype} | {c.null_pct:.1f} | {c.unique_ratio:.3f} | {_fmt(c.min)} | {_fmt(c.max)} | {'yes' if c.looks_like_time else 'no'}"
        )
    return "\n".join(lines)


def render_sample_rows(profile: DataProfile, limit: int = 20) -> str:
    rows = profile.sample_rows[:limit]
    if not rows:
        return "(no sample rows)"
    return json.dumps(rows, default=str)


def render_defaults(defaults: dict[str, Any] | None) -> str:
    if not defaults:
        return "No template defaults. Work out the target column from the profile and the user's goal."
    keep = {
        k: defaults.get(k)
        for k in ("target_column", "positive_label", "time_column", "primary_metric", "metric_params", "intake_goal", "economics_defaults")
        if k in defaults
    }
    return json.dumps(keep, default=str)


def render_checklist(spec: ProblemSpec | None) -> str:
    def mark(ok: bool) -> str:
        return "[x]" if ok else "[ ]"

    s = spec
    items = [
        (mark(bool(s and s.target_column)), "target column"),
        (mark(bool(s and (s.task_type == "regression" or s.positive_label is not None))), "positive label"),
        (mark(bool(s and s.metric_params)), "acceptable false alarms (fpr) or share to contact (top_k)"),
        (mark(bool(s and s.time_column is not None)), "time column, or confirmed none"),
        (mark(bool(s and s.economics)), "optional: money at stake per case and cost per action"),
    ]
    return "\n".join(f"{m} {label}" for m, label in items)


def build_system_prompt(
    *,
    template: str,
    profile: DataProfile,
    defaults: dict[str, Any] | None,
    spec: ProblemSpec | None,
    questions_asked: int,
) -> str:
    left = max(0, MAX_QUESTIONS - questions_asked)
    current = spec.model_dump(exclude={"constraints"}) if spec else None
    parts = [
        SYSTEM_PROMPT,
        f"Template: {template}. Questions you may still ask: {left}.",
        "Data profile:\n" + render_profile(profile),
        "Masked sample rows:\n" + render_sample_rows(profile),
        "Template defaults:\n" + render_defaults(defaults),
        "Current spec:\n" + json.dumps(current, default=str),
        "Checklist:\n" + render_checklist(spec),
    ]
    if left == 0:
        parts.append("You have no questions left. Confirm what you have and set done to true if the checklist is complete.")
    return "\n\n".join(parts)
