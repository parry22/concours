"""Promotion gates. A challenger replaces the active model only if it passes all five.

1. Hidden data   scored on the private holdout only; the public check never decides.
2. Same rows     a paired comparison with the active model on identical holdout days and transactions.
3. Luck test     day-block bootstrap: resample the holdout days with replacement (1,000 resamples, seeded); the
                 challenger must catch more fraud money in at least 95% of them.
4. Segments      no more than a 5% relative drop in fraud money caught in any segment: amount under 50, 50 to
                 500, over 500; new and returning customers.
5. Practical     scores 10,000 rows in under 5 seconds.

Pure functions over arrays so each gate is testable alone; `evaluate` runs them all.
"""
from __future__ import annotations

import numpy as np

from app.config import AMOUNT_BANDS, GATE_RESAMPLES, GATE_SECONDS_PER_10K, GATE_SEGMENT_DROP, GATE_WIN_SHARE, SPLIT_SEED
from app.models import FraudSettings, GateResult
from app.shared.metrics import fraud_queue

NAMES = {
    "hidden_data": "Hidden data",
    "same_rows": "Same rows",
    "luck": "Luck test",
    "segments": "No hidden regressions",
    "speed": "Practical",
}


def _money(x: float) -> str:
    return f"${x:,.0f}"


def hidden_data(split: str, private_score: float | None) -> GateResult:
    ok = split == "holdout" and private_score is not None
    line = "Scored on the private holdout only. The public check never decides." if ok else "Not scored on the private holdout."
    return GateResult(key="hidden_data", name=NAMES["hidden_data"], passed=ok, line=line, detail={"split": split})


def same_rows(challenger: np.ndarray | None, champion: np.ndarray | None, n_rows: int, n_days: int, champion_version: int) -> GateResult:
    ok = challenger is not None and champion is not None and len(challenger) == len(champion) == n_rows
    line = (f"Compared with v{champion_version} on the same {n_days} holdout days ({n_rows:,} transactions)." if ok
            else f"No score from v{champion_version} on these exact holdout rows.")
    return GateResult(key="same_rows", name=NAMES["same_rows"], passed=ok, line=line, detail={"rows": n_rows, "days": n_days})


def luck(challenger_by_day: np.ndarray, champion_by_day: np.ndarray, *, resamples: int = GATE_RESAMPLES,
         need: float = GATE_WIN_SHARE, seed: int = SPLIT_SEED) -> GateResult:
    """Day-block bootstrap on per-day caught amounts (paired: the same resampled days for both models)."""
    a = np.asarray(challenger_by_day, dtype=float)
    b = np.asarray(champion_by_day, dtype=float)
    n = len(a)
    if n == 0 or len(b) != n:
        return GateResult(key="luck", name=NAMES["luck"], passed=False, line="No holdout days to resample.", detail={})
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(resamples, n))
    wins = float(((a[idx].sum(axis=1) - b[idx].sum(axis=1)) > 0).mean())
    ok = wins >= need
    line = f"Wins in {wins:.0%} of resamples" + ("" if ok else f"; needs {need:.0%}")
    return GateResult(key="luck", name=NAMES["luck"], passed=ok, line=line,
                      detail={"win_share": round(wins, 4), "resamples": resamples, "need": need, "days": n,
                              "mean_gain_per_day": round(float((a - b).mean()), 2)})


def segment_masks(amount: np.ndarray, new_customer: np.ndarray) -> dict[str, np.ndarray]:
    lo, hi = AMOUNT_BANDS
    amount = np.asarray(amount, dtype=float)
    new = np.asarray(new_customer).astype(int) == 1
    return {
        f"Payments under {lo:g}": amount < lo,
        f"Payments {lo:g} to {hi:g}": (amount >= lo) & (amount <= hi),
        f"Payments over {hi:g}": amount > hi,
        "New customers": new,
        "Returning customers": ~new,
    }


def segments(y: np.ndarray, amount: np.ndarray, new_customer: np.ndarray, picked_challenger: np.ndarray,
             picked_champion: np.ndarray, *, max_drop: float = GATE_SEGMENT_DROP) -> GateResult:
    """Fraud money caught inside each segment by each model's queue (the queues are chosen over all rows)."""
    y = np.asarray(y).astype(int) == 1
    amount = np.asarray(amount, dtype=float)
    rows = []
    worst_name, worst = None, 0.0
    for name, m in segment_masks(amount, new_customer).items():
        champ = float(amount[m & y & picked_champion].sum())
        chal = float(amount[m & y & picked_challenger].sum())
        drop = (champ - chal) / champ if champ > 0 else 0.0
        rows.append({"segment": name, "champion": round(champ, 2), "challenger": round(chal, 2), "drop": round(drop, 4)})
        if drop > worst:
            worst_name, worst = name, drop
    ok = worst <= max_drop
    line = (f"No segment drops more than {max_drop:.0%}" if ok else f"{worst_name}: {worst:.0%} less fraud money caught")
    return GateResult(key="segments", name=NAMES["segments"], passed=ok, line=line, detail={"segments": rows, "max_drop": max_drop})


def speed(seconds_per_10k: float | None, *, limit: float = GATE_SECONDS_PER_10K) -> GateResult:
    ok = seconds_per_10k is not None and seconds_per_10k < limit
    line = (f"Scores 10,000 payments in {seconds_per_10k:.1f} s" if seconds_per_10k is not None else "Scoring time not measured")
    if not ok and seconds_per_10k is not None:
        line += f"; the limit is {limit:g} s"
    return GateResult(key="speed", name=NAMES["speed"], passed=ok, line=line, detail={"seconds_per_10k": seconds_per_10k, "limit": limit})


def evaluate(challenger_scores: np.ndarray, champion_scores: np.ndarray | None, y: np.ndarray, amount: np.ndarray, day: np.ndarray,
             new_customer: np.ndarray, settings: FraudSettings, *, champion_version: int, private_score: float | None,
             seconds_per_10k: float | None, split: str = "holdout") -> list[GateResult]:
    n = len(y)
    days = len(np.unique(np.asarray(day)))
    g1 = hidden_data(split, private_score)
    g2 = same_rows(challenger_scores, champion_scores, n, days, champion_version)
    if not g2.passed:
        empty = lambda k, why: GateResult(key=k, name=NAMES[k], passed=False, line=why, detail={})  # noqa: E731
        return [g1, g2, empty("luck", "Needs a paired comparison."), empty("segments", "Needs a paired comparison."), speed(seconds_per_10k)]
    kw = dict(capacity=settings.daily_capacity, fee=settings.fraud_fee, review_cost=settings.review_cost)
    qa = fraud_queue(y, challenger_scores, amount, day, **kw)
    qb = fraud_queue(y, champion_scores, amount, day, **kw)
    return [
        g1,
        g2,
        luck(qa["caught_amount_by_day"], qb["caught_amount_by_day"]),
        segments(y, amount, new_customer, qa["picked"], qb["picked"]),
        speed(seconds_per_10k),
    ]


def all_passed(gates: list[GateResult]) -> bool:
    return bool(gates) and all(g.passed for g in gates)
