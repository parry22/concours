"""Value-model parameters: measured from the data where possible, user overrides next, labeled defaults last.

Every parameter carries a source so the UI can say which numbers are facts and which are placeholders.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

import pandas as pd

from app.config import project_dir
from app.models import DataProfile, ParamSource, ProblemSpec, ProtectReport, ValueParam

KEYS = ("rows_per_month", "positive_rate", "value_per_positive", "action_success_rate", "cost_per_action", "cost_per_false_positive")
USER_KEYS = tuple(k for k in KEYS if k != "positive_rate")

# Old intake keys keep working. The old "cost of a false alarm" was the contact cost for churn.
ALIASES = {"monthly_volume": "rows_per_month", "cost_fn": "value_per_positive", "cost_fp": "cost_per_false_positive"}
ALIASES_BY_TEMPLATE = {"churn": {**ALIASES, "cost_fp": "cost_per_action"}}

UNITS = {
    "rows_per_month": "count",
    "positive_rate": "rate",
    "value_per_positive": "money",
    "action_success_rate": "rate",
    "cost_per_action": "money",
    "cost_per_false_positive": "money",
}

LABELS: dict[str, dict[str, str]] = {
    "fraud": {
        "rows_per_month": "Transactions per month",
        "positive_rate": "Share that is fraud",
        "value_per_positive": "Average fraud amount",
        "action_success_rate": "Share of flagged fraud that is stopped",
        "cost_per_action": "Cost to handle one flagged transaction",
        "cost_per_false_positive": "Cost of declining a good customer",
    },
    "churn": {
        "rows_per_month": "Customers scored per month",
        "positive_rate": "Share that leave",
        "value_per_positive": "Revenue kept per customer who stays",
        "action_success_rate": "Share of contacted leavers who stay",
        "cost_per_action": "Cost of one contact",
        "cost_per_false_positive": "Extra cost of contacting a customer who was staying anyway",
    },
    "custom": {
        "rows_per_month": "Rows per month",
        "positive_rate": "Share that is positive",
        "value_per_positive": "Value of acting on one true positive",
        "action_success_rate": "Share of flagged positives where the action works",
        "cost_per_action": "Cost of acting on one flagged row",
        "cost_per_false_positive": "Extra cost of a wrong flag",
    },
}

# Placeholders. Shown with the source "default" and a note; the user can replace them.
DEFAULTS: dict[str, dict[str, float]] = {
    "fraud": {"rows_per_month": 300_000, "value_per_positive": 120.0, "action_success_rate": 1.0, "cost_per_action": 0.0, "cost_per_false_positive": 4.0},
    "churn": {"rows_per_month": 3_000, "value_per_positive": 60.0, "action_success_rate": 0.25, "cost_per_action": 3.0, "cost_per_false_positive": 0.0},
    "custom": {"rows_per_month": 10_000, "value_per_positive": 100.0, "action_success_rate": 0.5, "cost_per_action": 1.0, "cost_per_false_positive": 1.0},
}

DEFAULT_NOTES = {
    "fraud": {
        "action_success_rate": "Assumes a flagged transaction is declined before the money leaves.",
        "cost_per_action": "Assumes automatic declines, no manual review.",
        "cost_per_false_positive": "Placeholder for lost margin and goodwill on a declined good transaction.",
        "value_per_positive": "Placeholder. Add an amount column to measure it.",
        "rows_per_month": "Placeholder. Add a time column to measure it.",
    },
    "churn": {
        "action_success_rate": "Placeholder. Retention campaigns typically keep 20% to 30% of the customers they reach.",
        "cost_per_action": "Placeholder for one call or offer.",
        "cost_per_false_positive": "Set this if an offer to a loyal customer costs more than the contact.",
        "value_per_positive": "Placeholder. Add a revenue or customer value column to measure it.",
        "rows_per_month": "Placeholder. The file is treated as one month of customers.",
    },
    "custom": {},
}

# Column name patterns for the money column, tried in order per template.
VALUE_COLUMN_PATTERNS = {
    "fraud": [r"amount|amt", r"value|price|total"],
    "churn": [r"customer.?value|ltv|lifetime|revenue|arpu|mrr", r"monthly.?charge|charge|amount|price"],
    "custom": [r"amount|amt|revenue|value|ltv|price|charge|total"],
}


def normalize_economics(econ: dict[str, Any] | None, template: str = "custom") -> dict[str, float]:
    """User-provided overrides only: aliases resolved, non-numbers and nulls dropped, positive_rate ignored."""
    aliases = ALIASES_BY_TEMPLATE.get(template, ALIASES)
    out: dict[str, float] = {}
    for k, v in (econ or {}).items():
        key = aliases.get(k, k)
        if key not in USER_KEYS or v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv >= 0:
            out[key] = fv
    return out


def _template(spec: ProblemSpec) -> str:
    t = spec.business_template if spec.business_template in LABELS else spec.template
    return t if t in LABELS else "custom"


def _months_spanned(report: ProtectReport | None) -> float | None:
    if not report:
        return None
    lo: datetime | None = None
    hi: datetime | None = None
    for p in report.parts:
        for v, pick in ((p.time_min, min), (p.time_max, max)):
            if not v:
                continue
            try:
                d = pd.Timestamp(v).to_pydatetime()
            except (ValueError, TypeError):
                continue
            lo = d if lo is None else min(lo, d)
            hi = d if hi is None else max(hi, d)
    if lo is None or hi is None or hi <= lo:
        return None
    return max((hi - lo).total_seconds() / (30.44 * 86400), 1 / 30.44)


def _find_value_column(columns: list[str], template: str, target: str) -> str | None:
    for pat in VALUE_COLUMN_PATTERNS.get(template, VALUE_COLUMN_PATTERNS["custom"]):
        rx = re.compile(pat, re.IGNORECASE)
        for c in columns:
            if c != target and rx.search(c):
                return c
    return None


def _measure_value_per_positive(project_id: str, template: str, target: str) -> tuple[float, str] | None:
    """Mean of the money column over positive rows of the protected train split. Cached per project."""
    protected = project_dir(project_id) / "protected"
    train = protected / "train.csv"
    if not train.exists():
        return None
    cache = project_dir(project_id) / "value" / "derived.json"
    stamp = f"{train.stat().st_mtime_ns}:{train.stat().st_size}"
    if cache.exists():
        try:
            d = json.loads(cache.read_text())
            if d.get("stamp") == stamp:
                return (d["value"], d["column"]) if d.get("value") is not None else None
        except (ValueError, KeyError):
            pass
    header = pd.read_csv(train, nrows=0).columns.tolist()
    col = _find_value_column(header, template, target)
    result: tuple[float, str] | None = None
    if col:
        df = pd.read_csv(train, usecols=[col, "label"])
        x = pd.to_numeric(df[col], errors="coerce")
        if x.nunique(dropna=True) > 2 and x.mean() > 0:
            pos = x[df["label"] == 1]
            mean = pos.mean() if len(pos.dropna()) >= 5 else x.mean()
            if pd.notna(mean) and mean > 0:
                result = (round(float(mean), 2), col)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"stamp": stamp, "value": result[0] if result else None, "column": result[1] if result else None}))
    return result


def resolve(project_id: str, spec: ProblemSpec, profile: DataProfile | None, report: ProtectReport | None) -> list[ValueParam]:
    """The six parameters with sources. Order: data < default, user on top; positive_rate is always measured."""
    template = _template(spec)
    labels = LABELS[template]
    defaults = DEFAULTS[template]
    notes = DEFAULT_NOTES.get(template, {})
    # A value equal to the placeholder is not information: older intake runs copied the placeholders into the spec.
    user = {k: v for k, v in normalize_economics(spec.economics, template).items() if abs(v - defaults.get(k, float("nan"))) > 1e-9}
    out: list[ValueParam] = []

    def add(key: str, value: float, source: ParamSource, note: str = "") -> None:
        out.append(ValueParam(key=key, label=labels[key], value=float(value), source=source, unit=UNITS[key], note=note))  # type: ignore[arg-type]

    # rows per month
    total_rows = sum(p.rows for p in report.parts) if report else (profile.n_rows if profile else 0)
    months = _months_spanned(report)
    if "rows_per_month" in user:
        add("rows_per_month", user["rows_per_month"], "user")
    elif months and total_rows:
        add("rows_per_month", round(total_rows / months), "data", f"{total_rows:,} rows over {months:.1f} months in the file.")
    elif total_rows and template == "churn":
        add("rows_per_month", total_rows, "default", notes.get("rows_per_month", ""))
    else:
        add("rows_per_month", defaults["rows_per_month"], "default", notes.get("rows_per_month", ""))

    # positive rate: always from the data
    if report and sum(p.rows for p in report.parts):
        pos = sum(p.positives for p in report.parts)
        add("positive_rate", pos / sum(p.rows for p in report.parts), "data", f"{pos:,} positives in the file.")
    elif profile and profile.positive_rate is not None:
        add("positive_rate", profile.positive_rate, "data", "Measured on the uploaded file.")
    else:
        add("positive_rate", 0.0, "default", "No positives found yet.")

    # value per positive
    if "value_per_positive" in user:
        add("value_per_positive", user["value_per_positive"], "user")
    else:
        measured = _measure_value_per_positive(project_id, template, spec.target_column)
        if measured:
            add("value_per_positive", measured[0], "data", f"Mean of {measured[1]} over positive rows in the training split.")
        else:
            add("value_per_positive", defaults["value_per_positive"], "default", notes.get("value_per_positive", ""))

    for key in ("action_success_rate", "cost_per_action", "cost_per_false_positive"):
        if key in user:
            add(key, user[key], "user")
        else:
            add(key, defaults[key], "default", notes.get(key, ""))
    return out


def as_dict(params: list[ValueParam]) -> dict[str, float]:
    return {p.key: p.value for p in params}


def params_hash(params: list[ValueParam]) -> str:
    return hashlib.sha256(json.dumps(as_dict(params), sort_keys=True).encode()).hexdigest()[:12]
