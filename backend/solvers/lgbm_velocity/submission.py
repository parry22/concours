"""LightGBM with entity history plus velocity features and card-testing rules.

Velocity is computed from past rows only and carried across the scoring stream (the referee sends rows in time
order, chunk after chunk): per terminal, payments and payments under 10 in the last hour; per customer,
payments in the last day, whether the card was used in a small-payment burst in the last three days, and
whether this terminal is new for the customer.

Card testing (many small payments at one terminal within minutes) is followed by cash-out purchases on the
tested cards at terminals the cardholder never used. Neither appears in older training data, so the model
alone cannot learn them; two rules lift their risk: a small payment inside a burst, and a payment on a card
tested in the last three days at a terminal new for that card. The cardholder's own purchases at their usual
terminals stay with the model.
"""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.base import SolverBase

SMALL = 10.0
HOUR = 3600.0
BURST = 4  # small payments at one terminal within the hour, this one excluded
KEEP_S = 72 * HOUR


def _pick(df: pd.DataFrame, words: tuple[str, ...]) -> str | None:
    for c in df.columns:
        if any(w in c.lower() for w in words) and pd.api.types.is_integer_dtype(df[c]):
            return c
    return None


def _window_count(keys: np.ndarray, t: np.ndarray, weight: np.ndarray, span: float) -> np.ndarray:
    """For each row, the sum of `weight` over earlier rows with the same key in [t - span, t)."""
    # one sorted axis: key blocks 1e10 seconds apart (t is seconds since 2000, far below that), so a window
    # never reaches into the previous key's block
    codes = np.unique(keys, return_inverse=True)[1].astype(float)
    comp = codes * 1e10 + np.asarray(t, dtype=float)
    order = np.argsort(comp, kind="stable")
    cs = comp[order]
    cw = np.r_[0.0, np.cumsum(np.asarray(weight, dtype=float)[order])]
    lo = np.searchsorted(cs, cs - span, side="left")
    hi = np.searchsorted(cs, cs, side="left")  # strictly earlier rows
    out = np.empty(len(t))
    out[order] = cw[hi] - cw[lo]
    return out


class Solver(SolverBase):
    name = "lgbm_velocity"
    history = True

    def __init__(self, transform=None):
        super().__init__(transform)
        self.buffer: pd.DataFrame | None = None
        self.cols: dict[str, str | None] = {}
        self.seen: set[tuple] = set()  # (customer, terminal) pairs met so far: training, then the stream

    # ---- velocity ----

    def _raw(self, df: pd.DataFrame) -> pd.DataFrame:
        tc = self.prep.time_column
        t = pd.to_datetime(df[tc], errors="coerce") if tc and tc in df.columns else pd.Series(pd.NaT, index=df.index)
        amt = self.cols.get("amount")
        return pd.DataFrame({
            "t": (t - pd.Timestamp("2000-01-01")).dt.total_seconds().fillna(0).to_numpy(),
            "term": df[self.cols["term"]].to_numpy() if self.cols.get("term") else np.zeros(len(df)),
            "cust": df[self.cols["cust"]].to_numpy() if self.cols.get("cust") else np.zeros(len(df)),
            "amount": df[amt].to_numpy(dtype=float) if amt else np.zeros(len(df)),
        })

    def _velocity(self, raw: pd.DataFrame, prior: pd.DataFrame | None) -> pd.DataFrame:
        """Features for `raw`'s rows, using `prior` (earlier rows) as history."""
        n = len(raw)
        allr = pd.concat([prior, raw], ignore_index=True) if prior is not None and len(prior) else raw.reset_index(drop=True)
        t, term, cust, amt = (allr[c].to_numpy() for c in ("t", "term", "cust", "amount"))
        small = (amt < SMALL).astype(float)
        term_n = _window_count(term, t, np.ones(len(t)), HOUR)
        term_small = _window_count(term, t, small, HOUR)
        in_burst = small * (term_small >= BURST)
        cust_n = _window_count(cust, t, np.ones(len(t)), 24 * HOUR)
        cust_tested = _window_count(cust, t, in_burst, KEEP_S)
        f = pd.DataFrame({"v_term_n_1h": term_n, "v_term_small_1h": term_small, "v_cust_n_24h": cust_n,
                          "v_cust_tested_72h": cust_tested, "v_in_burst": in_burst})
        return f.iloc[len(allr) - n:].reset_index(drop=True)

    def _new_terminal(self, raw: pd.DataFrame, *, learn: bool = True) -> np.ndarray:
        """1 when the customer has not paid at this terminal before (rows in time order)."""
        out = np.zeros(len(raw))
        for i, pair in enumerate(zip(raw["cust"].to_numpy(), raw["term"].to_numpy())):
            if pair not in self.seen:
                out[i] = 1.0
                if learn:
                    self.seen.add(pair)
        return out

    # ---- solver ----

    def fit_frame(self, train: pd.DataFrame) -> None:
        self.cols = {"term": _pick(train, ("terminal", "merchant")), "cust": _pick(train, ("customer",)),
                     "amount": "amount" if "amount" in train.columns else next((c for c in train.columns if pd.api.types.is_float_dtype(train[c])), None)}
        tc = self.prep.time_column
        if tc and tc in train.columns:
            train = train.iloc[np.argsort(pd.to_datetime(train[tc], errors="coerce").values, kind="stable")].reset_index(drop=True)
        X = self.prep.fit_transform(train)  # sorts by time again (stable): same order
        raw = self._raw(train)
        V = self._velocity(raw, None)
        self.seen = set()
        V["v_new_terminal"] = self._new_terminal(raw)
        X = pd.concat([X.reset_index(drop=True), V], axis=1)
        self.columns = list(X.columns)
        self.fit(X, self.prep.last_y)
        self.buffer = None

    def score_frame(self, df: pd.DataFrame) -> np.ndarray:
        X = self.prep.transform_batch(df).reset_index(drop=True)
        raw = self._raw(df)
        V = self._velocity(raw, self.buffer)
        V["v_new_terminal"] = self._new_terminal(raw)
        allr = pd.concat([self.buffer, raw], ignore_index=True) if self.buffer is not None else raw
        self.buffer = allr[allr["t"] >= allr["t"].max() - KEEP_S].reset_index(drop=True)
        X = pd.concat([X, V], axis=1)[self.columns]
        p = np.asarray(self.predict_proba(X), dtype=float)
        amt = raw["amount"].to_numpy()
        test = (V["v_in_burst"].to_numpy() > 0) & (amt < SMALL)
        cashout = (V["v_cust_tested_72h"].to_numpy() > 0) & (V["v_new_terminal"].to_numpy() > 0) & (amt >= SMALL)
        return np.maximum.reduce([p, np.where(test, 0.9, 0.0), np.where(cashout, 0.95, 0.0)])

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        pos = max(1, int(y.sum()))
        neg = max(1, len(y) - pos)
        self.model = lgb.LGBMClassifier(
            n_estimators=600, learning_rate=0.03, num_leaves=63, min_child_samples=40, subsample=0.8, subsample_freq=1,
            colsample_bytree=0.8, reg_lambda=1.0, scale_pos_weight=min(50.0, neg / pos), random_state=42, verbose=-1, n_jobs=2,
            # a larger payment is never less risky, all else equal (when the data has an amount column)
            monotone_constraints=[1 if c == "amount" else 0 for c in X.columns],
        )
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
