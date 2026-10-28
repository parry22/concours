"""Train / leaderboard / holdout split. Time-based when a time column exists, else stratified. Seed 42."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.config import SPLIT_SEED
from app.models import SplitPart

FRACTIONS = (0.70, 0.10, 0.20)


@dataclass
class Split:
    strategy: str
    train: pd.DataFrame
    leaderboard: pd.DataFrame
    holdout: pd.DataFrame

    def parts(self, target: str, positive) -> list[SplitPart]:
        return [_part(n, d, target, positive, self.strategy) for n, d in (("train", self.train), ("leaderboard", self.leaderboard), ("holdout", self.holdout))]


def _part(name: str, df: pd.DataFrame, target: str, positive, strategy: str, time_col: str | None = None) -> SplitPart:
    y = (df[target] == positive).astype(int) if target in df.columns else pd.Series(dtype=int)
    pos = int(y.sum()) if len(y) else 0
    part = SplitPart(name=name, rows=len(df), positives=pos, positive_rate=round(pos / len(df), 6) if len(df) else 0.0)  # type: ignore[arg-type]
    if "__t__" in df.columns and len(df):
        part.time_min = str(df["__t__"].min())
        part.time_max = str(df["__t__"].max())
    return part


def split_by_time(df: pd.DataFrame, time_col: str) -> Split:
    t = pd.to_datetime(df[time_col], errors="coerce")
    order = np.argsort(t.values, kind="stable")
    df = df.iloc[order].reset_index(drop=True)
    n = len(df)
    a = int(n * FRACTIONS[0])
    b = int(n * (FRACTIONS[0] + FRACTIONS[1]))
    return Split("time", df.iloc[:a].copy(), df.iloc[a:b].copy(), df.iloc[b:].copy())


def split_stratified(df: pd.DataFrame, target: str, seed: int = SPLIT_SEED) -> Split:
    rng = np.random.default_rng(seed)
    idx_train, idx_lb, idx_ho = [], [], []
    for _, grp in df.groupby(target, sort=False):
        idx = grp.index.to_numpy().copy()
        rng.shuffle(idx)
        n = len(idx)
        a = int(round(n * FRACTIONS[0]))
        b = int(round(n * (FRACTIONS[0] + FRACTIONS[1])))
        idx_train.extend(idx[:a])
        idx_lb.extend(idx[a:b])
        idx_ho.extend(idx[b:])
    return Split(
        "stratified",
        df.loc[sorted(idx_train)].reset_index(drop=True),
        df.loc[sorted(idx_lb)].reset_index(drop=True),
        df.loc[sorted(idx_ho)].reset_index(drop=True),
    )


def make_split(df: pd.DataFrame, target: str, time_col: str | None) -> Split:
    if time_col and time_col in df.columns:
        return split_by_time(df, time_col)
    return split_stratified(df, target)


def split_parts(s: Split, target: str, positive, time_col: str | None) -> list[SplitPart]:
    out = []
    for name, d in (("train", s.train), ("leaderboard", s.leaderboard), ("holdout", s.holdout)):
        y = (d[target] == positive).astype(int)
        pos = int(y.sum())
        p = SplitPart(name=name, rows=len(d), positives=pos, positive_rate=round(pos / len(d), 6) if len(d) else 0.0)  # type: ignore[arg-type]
        if time_col and time_col in d.columns and len(d):
            t = pd.to_datetime(d[time_col], errors="coerce")
            p.time_min, p.time_max = str(t.min()), str(t.max())
        out.append(p)
    return out
