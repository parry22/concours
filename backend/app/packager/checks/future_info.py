"""Future information: features computed with events after the transaction. Drop.

Two shapes are caught:
- a per-customer (or per-terminal) number that is the same on every row of the entity and tracks the entity's
  fraud count over the whole file, e.g. "customer_total_frauds" computed once over the full dataset. A model
  scoring a transaction could not have known the frauds that came after it.
- a timestamp column recorded after the transaction for most rows (a chargeback date, a review date).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.models import Finding
from app.packager.checks.base import CheckContext

ENTITY_COLUMNS = ("customer_id", "merchant_or_terminal_id")
MIN_CONSTANT_SHARE = 0.95  # of entities with 2+ rows, the share whose value never changes
MIN_CORR = 0.9
SKIP = {"amount", "transaction_id", "label_time", *ENTITY_COLUMNS}


def _entity_level(df: pd.DataFrame, entity: str, col: str) -> pd.Series | None:
    """The column's value per entity when it is constant within entities, else None."""
    g = df.groupby(entity, sort=False)[col]
    sizes = g.size()
    multi = sizes[sizes > 1].index
    if len(multi) < 10:
        return None
    nun = g.nunique(dropna=False).loc[multi]
    if (nun == 1).mean() < MIN_CONSTANT_SHARE:
        return None
    return g.first()


def _rank_corr(a: pd.Series, b: pd.Series) -> float:
    a, b = a.rank().to_numpy(dtype=float), b.rank().to_numpy(dtype=float)
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def run(ctx: CheckContext) -> None:
    df = ctx.df
    y = ctx.y
    for entity in (e for e in ENTITY_COLUMNS if e in df.columns):
        grp = pd.DataFrame({entity: df[entity].to_numpy(), "y": y.to_numpy()}).groupby(entity, sort=False)["y"]
        frauds, rows = grp.sum(), grp.size()
        for c in ctx.feature_columns:
            if c in SKIP or c == ctx.time_column or not pd.api.types.is_numeric_dtype(df[c]) or df[c].nunique() < 2:
                continue
            level = _entity_level(df, entity, c)
            if level is None:
                continue
            idx = level.index
            corr = max(abs(_rank_corr(level, frauds.loc[idx])), abs(_rank_corr(level, (frauds / rows).loc[idx])))
            if corr >= MIN_CORR:
                who = "customer" if entity == "customer_id" else "merchant or terminal"
                ctx.drop(Finding(
                    check="future_info",
                    severity="high",
                    column=c,
                    reason=(f"{c} is the same on every row of a {who} and follows that {who}'s fraud count over the whole file, "
                            "including frauds that happened later. A model scoring a transaction could not have known them."),
                    action="dropped",
                    evidence={"entity": entity, "rank_corr_with_fraud_count": round(corr, 3)},
                ))
    if ctx.time_column and ctx.time_column in df.columns:
        t = pd.to_datetime(df[ctx.time_column], errors="coerce")
        for c in ctx.feature_columns:
            if c in SKIP or c == ctx.time_column or pd.api.types.is_numeric_dtype(df[c]):
                continue
            text = df[c].dtype == object or pd.api.types.is_string_dtype(df[c])
            v = pd.to_datetime(df[c], errors="coerce", format="mixed") if text else None
            if v is None or v.notna().mean() < 0.5:
                continue
            later = ((v - t) > pd.Timedelta(hours=1)) & v.notna()
            share = float(later.sum() / max(1, v.notna().sum()))
            if share >= 0.5:
                ctx.drop(Finding(
                    check="future_info",
                    severity="high",
                    column=c,
                    reason=f"{c} is a date recorded after the transaction for {share:.0%} of rows. It is not known when the payment is scored.",
                    action="dropped",
                    evidence={"later_share": round(share, 3)},
                ))
