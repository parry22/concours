"""Business-language results. Deterministic templates; every number comes from code."""
from __future__ import annotations

from app.models import ProblemSpec
from app.shared.metrics import METRIC_NAMES
from app.templates import words


def _pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def business_card(spec: ProblemSpec, baseline: float, best: float, *, short: bool = False) -> str:
    t = spec.business_template
    w = words(spec.template, t)
    if t == "fraud" or spec.primary_metric == "recall_at_fpr":
        fpr = float(spec.metric_params.get("fpr", 0.001))
        per_1000 = fpr * 1000
        fa = f"{per_1000:g}"
        alarms = f"{fa} false alarm{'s' if per_1000 != 1 else ''} per 1,000 {w['negative']}"
        if short:
            return f"{_pct(best)} of {w['short']} caught at {alarms}"
        return f"{w['short'].capitalize()} caught at {alarms}: {_pct(baseline)} to {_pct(best)}."
    if t == "churn" or spec.primary_metric == "recall_at_top_k":
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
