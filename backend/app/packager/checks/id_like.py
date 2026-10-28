"""ID-like columns: unique ratio over 0.95, or a monotonic integer. Drop."""
from __future__ import annotations

import pandas as pd

from app.models import Finding
from app.packager.checks.base import CheckContext, time_derived


def run(ctx: CheckContext) -> None:
    n = len(ctx.df)
    for c in ctx.feature_columns:
        if time_derived(c, ctx.time_column):
            continue
        s = ctx.df[c]
        if pd.api.types.is_float_dtype(s):
            continue  # amounts and scores are high-cardinality but not IDs
        ratio = s.nunique(dropna=True) / n if n else 0
        monotonic = False
        if pd.api.types.is_integer_dtype(s) and n > 1:
            monotonic = bool(s.is_monotonic_increasing and s.nunique() > 0.5 * n)
        if ratio > 0.95 or monotonic:
            why = "nearly every row has its own value" if ratio > 0.95 else "it counts up row by row"
            ctx.drop(
                Finding(
                    check="id_like",
                    severity="medium",
                    column=c,
                    reason=f"{c} looks like an identifier: {why}. Identifiers do not generalize and can let solvers memorize rows.",
                    action="dropped",
                    evidence={"unique_ratio": round(float(ratio), 4), "monotonic": monotonic},
                )
            )
