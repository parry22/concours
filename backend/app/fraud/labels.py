"""Late labels. Fraud is confirmed weeks after the transaction, so every number must use only what was knowable.

Windows, working back from the as-of date E (whole days, D = label_delay_days):

    train | embargo (D days) | leaderboard (L days) | holdout (H days) | immature (D days) | after E (not yet seen)

- holdout ends D days before E: the newest window whose labels have had time to mature.
- immature: the newest D days. Never trained on or scored; used for today's queue and drift.
- embargo: D days between the training cutoff and the first evaluated day. Dropped from everything.
- training labels are as known at the training cutoff (the start of the embargo): a fraud confirmed later is
  label 0 there. Evaluation labels are as known at E.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.config import HOLDOUT_DAYS, LEADERBOARD_DAYS

MIN_TRAIN_DAYS = 14
PARTS = ("train", "embargo", "leaderboard", "holdout", "immature", "future")


@dataclass(frozen=True)
class Windows:
    as_of: pd.Timestamp  # the as-of day (00:00); everything up to the end of this day is known
    delay_days: int
    train_end: pd.Timestamp  # first day NOT in train (= embargo start = training cutoff)
    leaderboard_start: pd.Timestamp
    holdout_start: pd.Timestamp
    immature_start: pd.Timestamp  # first immature day (= day after the holdout)

    @property
    def as_of_end(self) -> pd.Timestamp:
        return self.as_of + pd.Timedelta(days=1)

    @property
    def holdout_end(self) -> pd.Timestamp:  # last holdout day
        return self.immature_start - pd.Timedelta(days=1)

    def iso(self) -> dict[str, str]:
        d = lambda x: x.strftime("%Y-%m-%d")  # noqa: E731
        return {
            "as_of": d(self.as_of),
            "train_end": d(self.train_end - pd.Timedelta(days=1)),
            "embargo_start": d(self.train_end),
            "embargo_end": d(self.leaderboard_start - pd.Timedelta(days=1)),
            "leaderboard_start": d(self.leaderboard_start),
            "holdout_start": d(self.holdout_start),
            "holdout_end": d(self.holdout_end),
            "immature_start": d(self.immature_start),
        }


def windows(as_of, delay_days: int, *, holdout_days: int = HOLDOUT_DAYS, leaderboard_days: int = LEADERBOARD_DAYS) -> Windows:
    day = pd.Timestamp(as_of).normalize()
    immature_start = day - pd.Timedelta(days=delay_days - 1)
    holdout_start = immature_start - pd.Timedelta(days=holdout_days)
    leaderboard_start = holdout_start - pd.Timedelta(days=leaderboard_days)
    train_end = leaderboard_start - pd.Timedelta(days=delay_days)
    return Windows(day, delay_days, train_end, leaderboard_start, holdout_start, immature_start)


def assign(t: pd.Series, w: Windows) -> pd.Series:
    """The window of each transaction time."""
    t = pd.to_datetime(t)
    part = pd.Series("future", index=t.index, dtype=object)
    part[t < w.as_of_end] = "immature"
    part[t < w.immature_start] = "holdout"
    part[t < w.holdout_start] = "leaderboard"
    part[t < w.leaderboard_start] = "embargo"
    part[t < w.train_end] = "train"
    return part


def known_label(is_fraud: pd.Series, label_time: pd.Series, at: pd.Timestamp) -> pd.Series:
    """1 only for frauds confirmed strictly before `at`: what a model or a scorer could know then."""
    lt = pd.to_datetime(label_time, errors="coerce")
    return ((is_fraud.astype(int) == 1) & lt.notna() & (lt < at)).astype(int)


def check_room(df: pd.DataFrame, w: Windows) -> None:
    first = pd.to_datetime(df["transaction_time"]).min().normalize()
    train_days = (w.train_end - first).days
    if train_days < MIN_TRAIN_DAYS:
        need = MIN_TRAIN_DAYS + 2 * w.delay_days + HOLDOUT_DAYS + LEADERBOARD_DAYS
        raise ValueError(
            f"Not enough history: with {w.delay_days} days to confirm fraud, the data needs about {need} days "
            f"before the as-of date, and it has {(w.as_of - first).days + 1}."
        )


def label_parts(df: pd.DataFrame, w: Windows) -> pd.DataFrame:
    """Adds `part`, `y_train` (known at the cutoff) and `y_eval` (known at the as-of date)."""
    out = df.copy()
    out["part"] = assign(out["transaction_time"], w)
    out["y_train"] = known_label(out["is_fraud"], out["label_time"], w.train_end)
    out["y_eval"] = known_label(out["is_fraud"], out["label_time"], w.as_of_end)
    return out


def summary_counts(df: pd.DataFrame) -> dict[str, int]:
    """Counts for the maturity summary, from a frame that went through `label_parts`."""
    tr = df["part"] == "train"
    ev = df["part"].isin(["leaderboard", "holdout"])
    return {
        "frauds_in_train": int(df.loc[tr, "is_fraud"].sum()),
        "frauds_unconfirmed_in_train": int(((df["is_fraud"] == 1) & (df["y_train"] == 0) & tr).sum()),
        "frauds_unconfirmed_at_eval": int(((df["is_fraud"] == 1) & (df["y_eval"] == 0) & ev).sum()),
        "embargo_rows": int((df["part"] == "embargo").sum()),
        "immature_rows": int((df["part"] == "immature").sum()),
    }
