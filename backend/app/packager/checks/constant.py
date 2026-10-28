"""Constant columns: one value in 99% or more of rows. Drop, severity info."""
from __future__ import annotations

from app.models import Finding
from app.packager.checks.base import CheckContext


def run(ctx: CheckContext) -> None:
    for c in ctx.feature_columns:
        s = ctx.df[c]
        if s.empty:
            continue
        top = s.value_counts(dropna=False, normalize=True).iloc[0]
        if top >= 0.99:
            ctx.drop(
                Finding(
                    check="constant",
                    severity="info",
                    column=c,
                    reason=f"{c} has the same value in {top:.1%} of rows, so it carries no signal.",
                    action="dropped",
                    evidence={"top_share": round(float(top), 4)},
                )
            )
