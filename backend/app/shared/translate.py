"""Business-language results. Deterministic templates; every number comes from code, the LLM never writes one."""
from __future__ import annotations

from app.models import ProblemSpec
from app.shared.metrics import LOWER_IS_BETTER, METRIC_NAMES
from app.templates import words


def _pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def _shape(spec: ProblemSpec) -> str:
    """fraud (caught at a false-alarm budget), reach (found in the riskiest share) or error (lower is better)."""
    t = spec.business_template
    if t == "fraud" or spec.primary_metric == "recall_at_fpr":
        return "fraud"
    if t == "churn" or spec.primary_metric == "recall_at_top_k":
        return "reach"
    return "error"


def metric_label(spec: ProblemSpec) -> str:
    """The scoring rule in plain words, without a number: 'Fraud caught at 1 false alarm per 1,000 good transactions'."""
    w = words(spec.template, spec.business_template)
    shape = _shape(spec)
    if shape == "fraud":
        per_1000 = float(spec.metric_params.get("fpr", 0.001)) * 1000
        fa = f"{per_1000:g}"
        return f"{w['short'].capitalize()} caught at {fa} false alarm{'s' if per_1000 != 1 else ''} per 1,000 {w['negative']}"
    if shape == "reach":
        k = float(spec.metric_params.get("top_k", 0.10))
        return f"{w['short'].capitalize()} reached in your top {_pct(k)}"
    return "Prediction error (lower is better)"


def short_label(spec: ProblemSpec) -> str:
    """Two or three words for table cells: 'Fraud caught', 'Buyers reached'."""
    w = words(spec.template, spec.business_template)
    shape = _shape(spec)
    if shape == "fraud":
        return f"{w['short'].capitalize()} caught"
    if shape == "reach":
        return f"{w['short'].capitalize()} reached"
    return "Error"


def fmt_score(spec: ProblemSpec, score: float) -> str:
    return f"{score:.3f}" if _shape(spec) == "error" else _pct(score)


def headline(spec: ProblemSpec, score: float) -> str:
    """One version's business line: 'Fraud caught at 1 false alarm per 1,000 good transactions: 84%'."""
    return f"{metric_label(spec)}: {fmt_score(spec, score)}"


def improvement_line(spec: ProblemSpec, v1_score: float, score: float) -> str:
    """'61% to 84% since your first model', or 'Your first model' when nothing changed."""
    if abs(score - v1_score) < 1e-12:
        return "Your first model"
    return f"{fmt_score(spec, v1_score)} to {fmt_score(spec, score)} since your first model"


def improvement_rel(spec: ProblemSpec, v1_score: float, score: float) -> float | None:
    """Relative gain over v1, direction-aware (a lower error counts as a gain)."""
    if v1_score == 0:
        return None
    if spec.primary_metric in LOWER_IS_BETTER:
        return (v1_score - score) / abs(v1_score)
    return (score - v1_score) / abs(v1_score)


def result_short(spec: ProblemSpec, v1_score: float | None, score: float) -> str:
    """Table cell: 'Buyers reached: 34% to 52%' or 'Buyers reached: 52%'."""
    if v1_score is None or abs(score - v1_score) < 1e-12:
        return f"{short_label(spec)}: {fmt_score(spec, score)}"
    return f"{short_label(spec)}: {fmt_score(spec, v1_score)} to {fmt_score(spec, score)}"


def business_card(spec: ProblemSpec, baseline: float, best: float, *, short: bool = False) -> str:
    """Kept for the leaderboard card and HANDOFF.md: '<label>: <baseline> to <best>.'"""
    w = words(spec.template, spec.business_template)
    shape = _shape(spec)
    if shape == "fraud":
        per_1000 = float(spec.metric_params.get("fpr", 0.001)) * 1000
        fa = f"{per_1000:g}"
        alarms = f"{fa} false alarm{'s' if per_1000 != 1 else ''} per 1,000 {w['negative']}"
        if short:
            return f"{_pct(best)} of {w['short']} caught at {alarms}"
        return f"{w['short'].capitalize()} caught at {alarms}: {_pct(baseline)} to {_pct(best)}."
    if shape == "reach":
        k = float(spec.metric_params.get("top_k", 0.10))
        if short:
            return f"{_pct(best)} of {w['short']} reached by contacting your riskiest {_pct(k)}"
        return f"Of {w['past']}, reached by contacting your riskiest {_pct(k)}: {_pct(baseline)} to {_pct(best)}."
    if short:
        return f"error {best:.3f}"
    return f"Prediction error: {baseline:.3f} to {best:.3f} (lower is better)."


def raw_metric_line(spec: ProblemSpec, baseline: float, best: float, finalized: bool) -> str:
    name = METRIC_NAMES.get(spec.primary_metric, spec.primary_metric)
    params = ", ".join(f"{k}={v}" for k, v in spec.metric_params.items())
    which = "private holdout" if finalized else "public leaderboard slice"
    return f"{name} ({params}) on the {which}: {baseline:.4f} to {best:.4f}"
