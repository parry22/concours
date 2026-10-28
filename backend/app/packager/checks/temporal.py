"""Temporal leakage: holdout must be strictly after train; leaderboard between. Fail split and re-split by time."""
from __future__ import annotations

import pandas as pd

from app.models import Finding
from app.packager.split import Split, split_by_time


def run(split: Split, time_column: str | None, findings: list[Finding]) -> Split:
    if not time_column or time_column not in split.train.columns:
        return split
    t_train = pd.to_datetime(split.train[time_column], errors="coerce")
    t_lb = pd.to_datetime(split.leaderboard[time_column], errors="coerce")
    t_ho = pd.to_datetime(split.holdout[time_column], errors="coerce")
    ok = t_train.max() <= t_lb.min() and t_lb.max() <= t_ho.min()
    if ok:
        return split
    full = pd.concat([split.train, split.leaderboard, split.holdout], ignore_index=True)
    new = split_by_time(full, time_column)
    findings.append(
        Finding(
            check="temporal",
            severity="high",
            column=time_column,
            reason="The hidden test rows were not strictly after the training rows, so solvers could have seen the future. The data was re-split by time.",
            action="resplit",
            evidence={"train_max": str(t_train.max()), "holdout_min": str(t_ho.min())},
        )
    )
    return new
