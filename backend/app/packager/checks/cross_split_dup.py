"""Cross-split duplicates: a row hash (excluding target) in train and holdout or leaderboard. Remove from train."""
from __future__ import annotations

import hashlib

import pandas as pd

from app.models import Finding
from app.packager.split import Split


def row_hashes(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    joined = df[cols].astype(str).fillna("").agg("\x1f".join, axis=1)  # astype(str) keeps NaN on pandas 3
    return joined.map(lambda s: hashlib.blake2b(s.encode(), digest_size=16).hexdigest())


def run(split: Split, feature_cols: list[str], findings: list[Finding]) -> int:
    if not feature_cols:
        return 0
    h_train = row_hashes(split.train, feature_cols)
    h_other = set(row_hashes(split.leaderboard, feature_cols)) | set(row_hashes(split.holdout, feature_cols))
    mask = h_train.isin(h_other)
    n = int(mask.sum())
    if n:
        split.train = split.train.loc[~mask].reset_index(drop=True)
        findings.append(
            Finding(
                check="cross_split_dup",
                severity="medium",
                column=None,
                reason=f"{n} training rows were exact copies of rows in the hidden test data. They were removed from training so solvers cannot memorize answers.",
                action="removed_rows",
                evidence={"rows_removed": n},
            )
        )
    return n
