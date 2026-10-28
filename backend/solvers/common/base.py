"""Solver base: plain Python, no Apex dependency. The player adapter (player/launch.py) wraps it.

A solver gets a training DataFrame (features + 'label') and must return scores for feature rows.
Feature preparation is shared so every solver sees the same columns; only modelling differs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TRANSFORM_PATH = Path("/app/data/transform.json")


def load_transform(path: Path = TRANSFORM_PATH) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


class FeaturePrep:
    """Deterministic feature engineering. Fit on train, apply to any batch (no label needed)."""

    def __init__(self, transform: dict[str, Any] | None = None, *, history: bool = False):
        self.transform = transform or {}
        self.time_column = self.transform.get("time_column")
        self.history = history
        self.cat_levels: dict[str, list] = {}
        self.columns: list[str] = []
        self.entity_stats: dict[str, dict] = {}
        self.entities: list[str] = []
        self.train_end_day: float = 0.0

    def _base(self, df: pd.DataFrame) -> pd.DataFrame:
        X = df.drop(columns=[c for c in ("label",) if c in df.columns]).copy()
        if self.time_column and self.time_column in X.columns:
            t = pd.to_datetime(X[self.time_column], errors="coerce")
            X["_hour"] = t.dt.hour.fillna(0).astype(int)
            X["_dow"] = t.dt.dayofweek.fillna(0).astype(int)
            X["_night"] = ((X["_hour"] < 6) | (X["_hour"] >= 22)).astype(int)
            X["_weekend"] = (X["_dow"] >= 5).astype(int)
            X = X.drop(columns=[self.time_column])
        return X

    @staticmethod
    def _entities(X: pd.DataFrame) -> list[str]:
        n = len(X)
        out = []
        for c in X.columns:
            l = c.lower()
            if not pd.api.types.is_integer_dtype(X[c]):
                continue
            if not any(k in l for k in ("id", "customer", "terminal", "merchant", "account", "device", "user")):
                continue
            nun = X[c].nunique()
            if 1 < nun < 0.5 * n:  # repeated entities, not a row id
                out.append(c)
        return out

    def _history_features(self, X: pd.DataFrame, y: np.ndarray | None, t: pd.Series | None, fit: bool) -> pd.DataFrame:
        """Per-entity history features using only information available before each row.

        At fit (train, sorted by time): for each entity, counts of previous transactions and previous positives,
        all-time and inside a 28-day window, plus the entity's mean amount so far. At prediction time the
        entity table frozen at the end of training is looked up (rows after training have no labels).
        """
        amount_cols = [c for c in X.columns if pd.api.types.is_float_dtype(X[c])]
        amount = amount_cols[0] if amount_cols else None
        if fit:
            self.entities = self._entities(X)
        if not self.entities:
            return X
        W = 28.0
        if fit and y is not None and t is not None:
            days = (t - t.min()).dt.total_seconds().to_numpy() / 86400.0
            if np.isnan(days).all():
                days = np.arange(len(X), dtype=float) / max(1, len(X))
            self.train_end_day = float(np.nanmax(days))
            amt = X[amount].to_numpy(dtype=float) if amount else None
            for e in self.entities:
                keys = X[e].to_numpy()
                prev_n = np.zeros(len(X)); prev_pos = np.zeros(len(X)); w_n = np.zeros(len(X)); w_pos = np.zeros(len(X)); prev_amt = np.zeros(len(X))
                table = {}
                # group indices by entity (train is already time-sorted)
                groups = pd.Series(np.arange(len(X))).groupby(keys).indices
                for k, idx in groups.items():
                    idx = np.asarray(idx)
                    d = days[idx]; yy = y[idx].astype(float)
                    cn = np.arange(len(idx), dtype=float)              # previous count
                    cp = np.concatenate([[0.0], np.cumsum(yy)[:-1]])  # previous positives
                    start = np.searchsorted(d, d - W, side="left")
                    cum_n = np.arange(1, len(idx) + 1, dtype=float); cum_p = np.cumsum(yy)
                    wn = cn - np.where(start > 0, cum_n[start - 1], 0.0)
                    wp = cp - np.where(start > 0, cum_p[start - 1], 0.0)
                    prev_n[idx] = cn; prev_pos[idx] = cp; w_n[idx] = wn; w_pos[idx] = wp
                    if amt is not None:
                        ca = np.concatenate([[0.0], np.cumsum(amt[idx])[:-1]])
                        prev_amt[idx] = np.where(cn > 0, ca / np.maximum(cn, 1), np.nan)
                    # frozen table for prediction time: all-time and last-W-days as of train end
                    ws = np.searchsorted(d, self.train_end_day - W, side="left")
                    table[k] = (float(len(idx)), float(yy.sum()), float(len(idx) - ws), float(yy[ws:].sum()), float(amt[idx].mean()) if amt is not None else np.nan)
                self.entity_stats[e] = table
                self._assign(X, e, prev_n, prev_pos, w_n, w_pos, prev_amt, amount)
        else:
            for e in self.entities:
                table = self.entity_stats.get(e, {})
                keys = X[e].to_numpy()
                rows = np.array([table.get(k, (0.0, 0.0, 0.0, 0.0, np.nan)) for k in keys], dtype=float).reshape(len(X), 5)
                self._assign(X, e, rows[:, 0], rows[:, 1], rows[:, 2], rows[:, 3], rows[:, 4], amount)
        return X

    @staticmethod
    def _assign(X, e, prev_n, prev_pos, w_n, w_pos, prev_amt, amount):
        X[f"{e}_prev_n"] = prev_n
        X[f"{e}_prev_pos"] = prev_pos
        X[f"{e}_prev_rate"] = (prev_pos + 0.1) / (prev_n + 10.0)
        X[f"{e}_w_n"] = w_n
        X[f"{e}_w_pos"] = w_pos
        X[f"{e}_w_rate"] = (w_pos + 0.1) / (w_n + 5.0)
        if amount is not None:
            X[f"{e}_prev_amt_mean"] = prev_amt
            X[f"{e}_amt_ratio"] = X[amount] / (np.nan_to_num(prev_amt, nan=X[amount].mean()) + 1e-6)

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.history and self.time_column and self.time_column in df.columns:
            t = pd.to_datetime(df[self.time_column], errors="coerce")
            order = np.argsort(t.values, kind="stable")
            df = df.iloc[order].reset_index(drop=True)
            t = t.iloc[order].reset_index(drop=True)
        else:
            t = None
        y = df["label"].to_numpy().astype(int) if "label" in df.columns else None
        X = self._base(df)
        self.entities = self._entities(X)
        if self.history:
            X = self._history_features(X, y, t, fit=True)
        # an entity ID's value means nothing (and is a salted hash for fraud); only its history aggregates are features
        X = X.drop(columns=[e for e in self.entities if e in X.columns])
        for c in X.columns:
            if X[c].dtype == object or pd.api.types.is_string_dtype(X[c]):
                levels = X[c].astype(str).value_counts().index[:50].tolist()
                self.cat_levels[c] = levels
                X[c] = pd.Categorical(X[c].astype(str), categories=levels).codes
        X = X.fillna(0)
        self.columns = list(X.columns)
        self.last_y = y
        return X

    def transform_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self._base(df)
        if self.history:
            X = self._history_features(X, None, None, fit=False)
        X = X.drop(columns=[e for e in self.entities if e in X.columns])
        for c, levels in self.cat_levels.items():
            if c in X.columns:
                X[c] = pd.Categorical(X[c].astype(str), categories=levels).codes
        for c in self.columns:
            if c not in X.columns:
                X[c] = 0
        return X[self.columns].fillna(0)


class SolverBase:
    """Implement fit(X, y) and predict_proba(X). `history` turns on entity aggregates."""

    name = "base"
    history = False

    def __init__(self, transform: dict[str, Any] | None = None):
        self.prep = FeaturePrep(transform, history=self.history)
        self.model: Any = None

    def fit_frame(self, train: pd.DataFrame) -> None:
        X = self.prep.fit_transform(train)
        self.fit(X, self.prep.last_y)

    def score_frame(self, df: pd.DataFrame) -> np.ndarray:
        X = self.prep.transform_batch(df)
        return np.asarray(self.predict_proba(X), dtype=float)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        raise NotImplementedError

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError
