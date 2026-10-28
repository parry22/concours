"""Top reasons per queued case, in plain English.

Tree models: LightGBM `pred_contrib` (per-feature contributions to the log-odds). Logistic regression:
coefficient x standardized value. Velocity rules add their own reason when they fire. Feature names never
reach the screen: each maps to a sentence here.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

TOP = 3

# (pattern on the feature name, reason), first match wins
RULES: list[tuple[str, str]] = [
    (r"^v_in_burst$|^v_term_small_1h$", "Card-testing burst at this terminal"),
    (r"^v_cust_tested_72h$", "Card was tested in the last 3 days"),
    (r"^v_term_n_1h$", "Many payments at this terminal in the last hour"),
    (r"^v_cust_n_24h$", "Many payments on this card today"),
    (r"^v_new_terminal$", "First payment at this terminal for this card"),
    (r"(customer).*_amt_ratio$", "Unusual amount for this customer"),
    (r"(terminal|merchant).*_amt_ratio$", "Unusual amount for this terminal"),
    (r"(customer).*_prev_amt_mean$", "This customer's usual spending"),
    (r"(terminal|merchant).*_w_(rate|pos)$", "Terminal had recent fraud"),
    (r"(terminal|merchant).*_prev_(rate|pos)$", "Terminal has a fraud history"),
    (r"(customer).*_w_(rate|pos)$", "Customer had recent fraud"),
    (r"(customer).*_prev_(rate|pos)$", "Customer has a fraud history"),
    (r"(terminal|merchant).*_(w_n|prev_n)$", "Unusual activity at this terminal"),
    (r"(customer).*_(w_n|prev_n)$", "Unusual activity on this card"),
    (r"^amount$", "Unusual amount"),
    (r"^_night$", "Night-time payment"),
    (r"^_hour$", "Time of day"),
    (r"^_(dow|weekend)$", "Day of the week"),
    (r"time_(seconds|days)$", "Timing"),
    (r"^currency$", "Currency"),
]


def describe(feature: str) -> str:
    for pat, text in RULES:
        if re.search(pat, feature, flags=re.I):
            return text
    return re.sub(r"[_\s]+", " ", feature).strip().capitalize() + " value"


def contributions(solver, X: pd.DataFrame) -> np.ndarray | None:
    """(rows, features) contributions toward fraud, or None when the model type is unknown."""
    models = getattr(solver, "models", None) or [getattr(solver, "model", None)]
    mats = []
    for m in models:
        if m is None:
            continue
        booster = getattr(m, "booster_", None)
        if booster is not None:
            mats.append(np.asarray(booster.predict(X, pred_contrib=True))[:, :-1])  # last column is the bias
            continue
        steps = getattr(m, "named_steps", None)
        if steps:
            scaler = next((s for s in steps.values() if hasattr(s, "scale_")), None)
            clf = next((s for s in steps.values() if hasattr(s, "coef_")), None)
            if clf is not None:
                Z = scaler.transform(X) if scaler is not None else X.to_numpy(dtype=float)
                mats.append(np.asarray(Z) * np.asarray(clf.coef_).ravel())
    if not mats:
        return None
    return np.mean(mats, axis=0)


def top_reasons(contrib: np.ndarray | None, columns: list[str], extra: list[list[str]] | None = None, k: int = TOP) -> list[list[tuple[str, float]]]:
    """Per row, up to k (text, weight) pairs with the largest positive contributions; the same sentence from
    two features is merged. `extra` puts rule reasons first."""
    n = len(extra) if contrib is None and extra is not None else (contrib.shape[0] if contrib is not None else 0)
    texts = [describe(c) for c in columns]
    out = []
    for i in range(n):
        merged: dict[str, float] = {}
        for text in (extra[i] if extra else []):
            merged[text] = merged.get(text, 0.0) + 10.0  # a rule that fired leads
        if contrib is not None:
            for j, v in enumerate(contrib[i]):
                if v > 0:
                    merged[texts[j]] = merged.get(texts[j], 0.0) + float(v)
        ranked = sorted(merged.items(), key=lambda kv: -kv[1])[:k]
        out.append([(t, round(w, 4)) for t, w in ranked])
    return out


def explain(solver, frame: pd.DataFrame, rows: np.ndarray) -> list[list[tuple[str, float]]]:
    """Reasons for `rows` (positions in `frame`). `frame` is a time-ordered window so velocity has history."""
    X = solver.prep.transform_batch(frame).reset_index(drop=True)
    extra = None
    if hasattr(solver, "_velocity"):
        raw = solver._raw(frame)
        V = solver._velocity(raw, None)
        V["v_new_terminal"] = solver._new_terminal(raw, learn=False)
        X = pd.concat([X, V], axis=1)[solver.columns]
        amt = raw["amount"].to_numpy()
        extra = []
        for i in range(len(frame)):
            r = []
            if V.at[i, "v_in_burst"] > 0 and amt[i] < 10:
                r.append("Card-testing burst at this terminal")
            if V.at[i, "v_cust_tested_72h"] > 0 and V.at[i, "v_new_terminal"] > 0 and amt[i] >= 10:
                r.append("Card was tested in the last 3 days")
            extra.append(r)
    Xs = X.iloc[rows]
    contrib = contributions(solver, Xs)
    return top_reasons(contrib, list(Xs.columns), [extra[i] for i in rows] if extra is not None else None)
