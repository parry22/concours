"""Business-language results. Deterministic templates; every number comes from code."""
from __future__ import annotations

from app.models import ProblemSpec
from app.shared.metrics import METRIC_NAMES


def _pct(x: float) -> str:
    return f"{round(x * 100):d}%"


def business_card(spec: ProblemSpec, baseline: float, best: float, *, short: bool = False) -> str:
    t = spec.business_template
    if t == "fraud" or spec.primary_metric == "recall_at_fpr":
        fpr = float(spec.metric_params.get("fpr", 0.001))
        per_1000 = fpr * 1000
        fa = f"{per_1000:g}"
        if short:
            return f"{_pct(best)} of fraud caught at {fa} false alarm{'s' if per_1000 != 1 else ''} per 1,000 good transactions"
        return f"Fraud caught at {fa} false alarm{'s' if per_1000 != 1 else ''} per 1,000 good transactions: {_pct(baseline)} to {_pct(best)}."
    if t == "churn" or spec.primary_metric == "recall_at_top_k":
        k = float(spec.metric_params.get("top_k", 0.10))
        if short:
            return f"{_pct(best)} of leavers reached by contacting your riskiest {_pct(k)}"
        return f"Of customers who left, reached by contacting your riskiest {_pct(k)}: {_pct(baseline)} to {_pct(best)}."
    if short:
        return f"error {best:.3f}"
    return f"Prediction error: {baseline:.3f} to {best:.3f} (lower is better)."


def raw_metric_line(spec: ProblemSpec, baseline: float, best: float, finalized: bool) -> str:
    name = METRIC_NAMES.get(spec.primary_metric, spec.primary_metric)
    params = ", ".join(f"{k}={v}" for k, v in spec.metric_params.items())
    which = "private holdout" if finalized else "public leaderboard slice"
    return f"{name} ({params}) on the {which}: {baseline:.4f} to {best:.4f}"


def savings(spec: ProblemSpec, baseline: float, best: float) -> tuple[str | None, str | None]:
    """Monthly savings from catching more positives at the same false-alarm budget."""
    e = spec.economics or {}
    try:
        volume = float(e.get("monthly_volume") or 0)
        cost_fn = float(e.get("cost_fn") or 0)
    except (TypeError, ValueError):
        return None, None
    if volume <= 0 or cost_fn <= 0:
        return None, None
    rate = float(e.get("positive_rate") or 0)
    if rate <= 0:
        return None, None
    extra_caught = volume * rate * max(0.0, best - baseline)
    amount = extra_caught * cost_fn
    line = f"Estimated monthly savings: ${amount:,.0f}"
    formula = f"{volume:,.0f} rows per month x {rate:.2%} positive rate x ({_pct(best)} - {_pct(baseline)}) caught x ${cost_fn:,.0f} per missed case"
    return line, formula
