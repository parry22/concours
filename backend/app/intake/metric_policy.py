"""Deterministic metric policy. The LLM proposes; this module decides.

Binary, positive rate under 5%  -> recall_at_fpr   (fpr, default 0.001), secondary pr_auc,  business "fraud"
Binary, positive rate 5% or more -> recall_at_top_k (top_k, default 0.10), secondary roc_auc, business "churn"
Regression                       -> wape, secondary mae, business "regression"
"""
from __future__ import annotations

from typing import Any

from app.models import ColumnProfile, DataProfile, ProblemSpec
from app.templates import rate_hint, words

RARE_THRESHOLD = 0.05
FPR_DEFAULT = 0.001
FPR_MIN, FPR_MAX = 0.0001, 0.05
TOP_K_DEFAULT = 0.10
TOP_K_MIN, TOP_K_MAX = 0.01, 0.5

# Plain words (what a positive is, what a negative row is called) and the rough positive rate used when neither
# the profile nor the caller gives one come from data/templates/<template>/defaults.json, see app.templates.


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _as_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def target_profile(profile: DataProfile, spec: ProblemSpec) -> ColumnProfile | None:
    return next((c for c in profile.columns if c.name == spec.target_column), None)


def estimate_positive_rate(profile: DataProfile, spec: ProblemSpec) -> float | None:
    """profile.positive_rate when it was measured on the spec's target (or on an unrecorded column, older profiles),
    else a rough estimate from the masked sample rows, else None."""
    if profile.positive_rate is not None and profile.positive_rate_column in (None, spec.target_column):
        return float(profile.positive_rate)
    if not spec.target_column or spec.positive_label is None or not profile.sample_rows:
        return None
    vals = [r.get(spec.target_column) for r in profile.sample_rows if spec.target_column in r]
    if not vals:
        return None
    hits = sum(1 for v in vals if str(v) == str(spec.positive_label))
    return hits / len(vals)


def looks_like_regression(profile: DataProfile, spec: ProblemSpec) -> bool:
    """A numeric target with many distinct values is a number to predict, not a yes/no."""
    if spec.task_type == "regression":
        return True
    col = target_profile(profile, spec)
    if col is None:
        return False
    numeric = col.dtype.lower().startswith(("float", "int", "number"))
    return numeric and col.n_unique > 20 and col.unique_ratio > 0.05


def _fmt_rate_as_one_in(rate: float) -> str:
    if rate <= 0:
        return "almost none of the"
    n = max(2, round(1 / rate))
    return f"about 1 in {n:,}"


def _fmt_count(x: float) -> str:
    return f"{x:,.0f}" if abs(x - round(x)) < 1e-9 else f"{x:,.2g}"


def rationale_fraud(rate: float | None, fpr: float, template: str, business: str = "fraud") -> str:
    w = words(template, business)
    pos, neg = w["positive"], w["negative"]
    per_1000 = fpr * 1000
    alarms = "1 false alarm" if abs(per_1000 - 1) < 1e-9 else f"{_fmt_count(per_1000)} false alarms"
    if rate is None:
        lead = f"Very few rows are {pos}"
    elif rate < 0.01:
        lead = f"Fewer than 1 in 100 rows are {pos}"
    else:
        lead = f"Only {_fmt_rate_as_one_in(rate)} rows are {pos}"
    return f"{lead}, so we measure how much {pos} is caught at {alarms} per 1,000 {neg}."


def rationale_churn(rate: float | None, top_k: float, template: str, business: str = "churn") -> str:
    w = words(template, business)
    pos, neg, short = w["positive"], w["negative"], w["short"]
    pct_k = _fmt_count(top_k * 100)
    if rate is None:
        lead = f"A fair share of rows are {pos}"
    else:
        lead = f"About {_fmt_count(rate * 100)} in 100 rows are {pos}"
    return f"{lead}, so we measure how many {short} you reach by contacting the riskiest {pct_k}% of {neg}."


def rationale_regression() -> str:
    return "The target is a number, so we measure how far predictions land from the real values as a share of the total."


def decide_metric(
    profile: DataProfile,
    spec: ProblemSpec,
    *,
    positive_rate: float | None = None,
) -> ProblemSpec:
    """Return a copy of spec with metric fields set by policy. Overrides conflicting LLM proposals."""
    params: dict[str, Any] = dict(spec.metric_params or {})

    if looks_like_regression(profile, spec):
        return spec.model_copy(
            update={
                "task_type": "regression",
                "positive_label": None,
                "primary_metric": "wape",
                "metric_params": {},
                "secondary_metric": "mae",
                "business_template": "regression",
                "metric_rationale": rationale_regression(),
            }
        )

    rate = positive_rate if positive_rate is not None else estimate_positive_rate(profile, spec)
    if rate is None:
        rate = rate_hint(spec.template)

    rare = rate is None or rate < RARE_THRESHOLD
    if rare:
        fpr = _as_float(params.get("fpr"))
        fpr = clamp(fpr if fpr is not None else FPR_DEFAULT, FPR_MIN, FPR_MAX)
        business = "fraud"
        return spec.model_copy(
            update={
                "task_type": "binary",
                "primary_metric": "recall_at_fpr",
                "metric_params": {"fpr": fpr},
                "secondary_metric": "pr_auc",
                "business_template": business,
                "metric_rationale": rationale_fraud(rate, fpr, spec.template, business),
            }
        )

    top_k = _as_float(params.get("top_k"))
    top_k = clamp(top_k if top_k is not None else TOP_K_DEFAULT, TOP_K_MIN, TOP_K_MAX)
    business = "churn"
    return spec.model_copy(
        update={
            "task_type": "binary",
            "primary_metric": "recall_at_top_k",
            "metric_params": {"top_k": top_k},
            "secondary_metric": "roc_auc",
            "business_template": business,
            "metric_rationale": rationale_churn(rate, top_k, spec.template, business),
        }
    )


def spec_is_complete(spec: ProblemSpec | None) -> bool:
    """True when target, positive label (binary only), primary metric and its params are set."""
    if spec is None or not spec.target_column:
        return False
    if spec.task_type == "binary" and spec.positive_label is None:
        return False
    if not spec.primary_metric:
        return False
    if spec.primary_metric == "recall_at_fpr":
        return "fpr" in spec.metric_params
    if spec.primary_metric == "recall_at_top_k":
        return "top_k" in spec.metric_params
    return True
