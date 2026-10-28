"""Scoring metrics shared by the referee image and the backend. Pure numpy, no sklearn, so the referee image stays small.

All functions take y_true (0/1 ints) and scores (higher = more likely positive) and return a float in [0, 1]
(higher is better) except wape/mae which are errors (lower is better).
"""
from __future__ import annotations

import numpy as np

METRIC_NAMES = {
    "recall_at_fpr": "Recall at fixed false-positive rate",
    "recall_at_top_k": "Recall in the top k% of scored rows",
    "pr_auc": "Precision-recall AUC",
    "roc_auc": "ROC AUC",
    "wape": "Weighted absolute percentage error",
    "mae": "Mean absolute error",
    "fraud_amount_per_day": "Fraud amount caught per day within review capacity",
}
LOWER_IS_BETTER = {"wape", "mae"}


def _prep(y_true, scores):
    y = np.asarray(y_true).astype(int).ravel()
    s = np.asarray(scores, dtype=float).ravel()
    if y.shape != s.shape:
        raise ValueError(f"shape mismatch {y.shape} vs {s.shape}")
    s = np.nan_to_num(s, nan=-np.inf, posinf=np.finfo(float).max, neginf=-np.inf)
    return y, s


def threshold_at_fpr(y_true, scores, fpr: float) -> float:
    """Smallest threshold such that at most `fpr` of negatives score >= threshold. Flag = score >= threshold."""
    y, s = _prep(y_true, scores)
    neg = np.sort(s[y == 0])[::-1]
    if len(neg) == 0:
        return float(np.min(s)) if len(s) else 0.0
    k = int(np.floor(fpr * len(neg)))  # number of negatives allowed above threshold
    if k == 0:
        return float(np.nextafter(neg[0], np.inf))
    return float(neg[k - 1]) if k <= len(neg) else float(neg[-1])


def recall_at_fpr(y_true, scores, fpr: float = 0.001) -> float:
    y, s = _prep(y_true, scores)
    if y.sum() == 0:
        return 0.0
    # Use strict ranking: count negatives strictly above a positive's score.
    neg = np.sort(s[y == 0])
    allowed = int(np.floor(fpr * len(neg)))
    if len(neg) == 0:
        return 1.0
    # threshold = the (allowed+1)-th highest negative score; positives must beat all but `allowed` negatives
    idx = len(neg) - allowed - 1
    if idx < 0:
        thr = -np.inf
    else:
        thr = neg[idx]
    pos = s[y == 1]
    return float(np.mean(pos > thr))


def recall_at_top_k(y_true, scores, top_k: float = 0.10) -> float:
    y, s = _prep(y_true, scores)
    if y.sum() == 0:
        return 0.0
    n = max(1, int(np.ceil(top_k * len(s))))
    order = np.argsort(-s, kind="stable")
    top = order[:n]
    return float(y[top].sum() / y.sum())


def roc_auc(y_true, scores) -> float:
    y, s = _prep(y_true, scores)
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    # rank-based with tie handling
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def pr_auc(y_true, scores) -> float:
    """Average precision (step-wise area under the precision-recall curve). Ties are grouped, as sklearn does."""
    y, s = _prep(y_true, scores)
    n_pos = int(y.sum())
    if n_pos == 0:
        return 0.0
    order = np.argsort(-s, kind="stable")
    y_sorted, s_sorted = y[order], s[order]
    # group boundaries: last index of each run of equal scores
    distinct = np.where(np.diff(s_sorted) != 0)[0]
    ends = np.r_[distinct, len(s_sorted) - 1]
    tp = np.cumsum(y_sorted)[ends]
    precision = tp / (ends + 1)
    recall = tp / n_pos
    prev_recall = np.r_[0.0, recall[:-1]]
    return float(((recall - prev_recall) * precision).sum())


def wape(y_true, y_pred) -> float:
    y = np.asarray(y_true, dtype=float).ravel()
    p = np.asarray(y_pred, dtype=float).ravel()
    denom = np.abs(y).sum()
    return float(np.abs(y - p).sum() / denom) if denom else 0.0


def mae(y_true, y_pred) -> float:
    y = np.asarray(y_true, dtype=float).ravel()
    p = np.asarray(y_pred, dtype=float).ravel()
    return float(np.abs(y - p).mean()) if len(y) else 0.0


def fraud_queue(y_true, scores, amount, day, capacity: int = 200, fee: float = 0.0, review_cost: float = 0.0) -> dict:
    """Capacity-based fraud evaluation. For each day, rank that day's transactions by expected loss
    (score x (amount + fee)) and review the top `capacity`. Money-weighted: what matters is the fraud amount
    inside the reviewed cases.

    Returns per-day arrays (for the promotion gates) and the summary numbers:
      amount_per_day   mean fraud amount caught per day (the primary metric)
      count_per_day    mean frauds caught per day
      precision        share of reviewed cases that were fraud
      false_alarms_per_1000  reviewed legitimate cases per 1,000 legitimate transactions
      net_per_day      amount_per_day - capacity x review_cost
      share            fraud amount caught / all fraud amount
    """
    y, s = _prep(y_true, scores)
    amt = np.nan_to_num(np.asarray(amount, dtype=float).ravel(), nan=0.0)
    days = np.asarray(day).ravel()
    if not (len(y) == len(amt) == len(days)):
        raise ValueError("y, scores, amount and day must have the same length")
    uniq, codes = np.unique(days, return_inverse=True)
    n_days = len(uniq)
    el = s * (amt + fee)
    el = np.where(np.isfinite(el), el, -np.inf)
    order = np.lexsort((-el, codes))  # by day, then expected loss descending
    sorted_codes = codes[order]
    first = np.searchsorted(sorted_codes, np.arange(n_days), side="left")
    rank = np.arange(len(order)) - first[sorted_codes]
    picked = np.zeros(len(y), dtype=bool)
    picked[order[rank < capacity]] = True
    caught = picked & (y == 1)
    caught_amount = np.bincount(codes, weights=np.where(caught, amt, 0.0), minlength=n_days)
    caught_count = np.bincount(codes, weights=caught.astype(float), minlength=n_days)
    fraud_amount = np.bincount(codes, weights=np.where(y == 1, amt, 0.0), minlength=n_days)
    reviewed = np.bincount(codes, weights=picked.astype(float), minlength=n_days)
    legit = int((y == 0).sum())
    false_alarms = int((picked & (y == 0)).sum())
    amount_per_day = float(caught_amount.mean()) if n_days else 0.0
    return {
        "days": [str(d) for d in uniq],
        "caught_amount_by_day": caught_amount,
        "caught_count_by_day": caught_count,
        "fraud_amount_by_day": fraud_amount,
        "reviewed_by_day": reviewed,
        "picked": picked,
        "amount_per_day": amount_per_day,
        "count_per_day": float(caught_count.mean()) if n_days else 0.0,
        "precision": float(caught.sum() / picked.sum()) if picked.sum() else 0.0,
        "false_alarms_per_1000": float(false_alarms / legit * 1000) if legit else 0.0,
        "net_per_day": amount_per_day - capacity * review_cost,
        "share": float(caught_amount.sum() / fraud_amount.sum()) if fraud_amount.sum() else 0.0,
        "fraud_per_day": float(fraud_amount.mean()) if n_days else 0.0,
    }


def fraud_summary(q: dict) -> dict:
    """The JSON-safe part of `fraud_queue` for result.json."""
    return {k: q[k] for k in ("amount_per_day", "count_per_day", "precision", "false_alarms_per_1000", "net_per_day", "share", "fraud_per_day")} | {
        "days": q["days"], "caught_amount_by_day": [round(float(v), 2) for v in q["caught_amount_by_day"]],
    }


def compute(name: str, y_true, scores, params: dict | None = None, meta: dict | None = None) -> float:
    """`meta` carries per-row `amount` and `day` for the capacity metric."""
    params = params or {}
    if name == "fraud_amount_per_day":
        if not meta:
            raise ValueError("fraud_amount_per_day needs per-row amount and day")
        return fraud_queue(y_true, scores, meta["amount"], meta["day"], int(params.get("capacity", 200)),
                           float(params.get("fee", 0.0)), float(params.get("review_cost", 0.0)))["amount_per_day"]
    if name == "recall_at_fpr":
        return recall_at_fpr(y_true, scores, float(params.get("fpr", 0.001)))
    if name == "recall_at_top_k":
        return recall_at_top_k(y_true, scores, float(params.get("top_k", 0.10)))
    if name == "pr_auc":
        return pr_auc(y_true, scores)
    if name == "roc_auc":
        return roc_auc(y_true, scores)
    if name == "wape":
        return wape(y_true, scores)
    if name == "mae":
        return mae(y_true, scores)
    raise ValueError(f"unknown metric {name}")
