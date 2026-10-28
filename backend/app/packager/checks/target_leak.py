"""Target leakage: single-feature AUC over 0.99, or over 0.95 with a post-outcome name. Drop, severity high."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from app.models import Finding
from app.packager.checks.base import CheckContext
from app.packager.checks.post_outcome_name import matches

AUC_HARD = 0.99
AUC_SOFT = 0.95
SAMPLE_ROWS = 50_000


def single_feature_auc(x: pd.Series, y: pd.Series) -> float | None:
    if y.nunique() < 2:
        return None
    if pd.api.types.is_numeric_dtype(x):
        v = x.fillna(x.median() if x.notna().any() else 0).astype(float).to_numpy()
    else:
        # categorical: encode by positive rate per category (target encoding on the same sample)
        rate = y.groupby(x.astype(str)).mean()
        v = x.astype(str).map(rate).fillna(y.mean()).to_numpy()
    if np.all(v == v[0]):
        return None
    auc = float(roc_auc_score(y, v))
    return max(auc, 1 - auc)


def run(ctx: CheckContext) -> None:
    df = ctx.df
    if len(df) > SAMPLE_ROWS:
        df = df.sample(n=SAMPLE_ROWS, random_state=42)
    y = (df[ctx.target] == ctx.positive).astype(int)
    for c in ctx.feature_columns:
        if c == ctx.time_column:
            continue
        auc = single_feature_auc(df[c], y)
        if auc is None:
            continue
        named = matches(c)
        if auc > AUC_HARD or (auc > AUC_SOFT and named):
            ctx.drop(
                Finding(
                    check="target_leak",
                    severity="high",
                    column=c,
                    reason=f"This column would let solvers cheat: on its own it predicts the outcome almost perfectly, which means it is only filled in after the outcome is known.",
                    action="dropped",
                    evidence={"single_feature_auc": round(auc, 4), "post_outcome_name": named},
                )
            )
