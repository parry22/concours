"""Inject a new fraud pattern into the fraud sample: card testing followed by cash-outs. Our own code.

From `--start-day` (days after the first transaction), fraudsters control a set of compromised terminals. Every
day they run short bursts there: many payments under $10 within minutes, each on a different stolen card (an
existing customer). Within one to three days, about half of the tested cards are used for cash-out purchases at
other terminals, sized like the customer's own spending (so the amount ranking the model already has does
not catch them). All injected payments are fraud. Seeded and reproducible.

  python scripts/inject_drift.py [--src transactions.csv] [--out transactions_drift.csv] [--start-day 128]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data" / "templates" / "fraud"
TEST_SCENARIO, CASHOUT_SCENARIO = 4, 5


def inject(df: pd.DataFrame, *, start_day: int = 128, terminals: int = 40, bursts_per_day: int = 4, burst_size: tuple[int, int] = (12, 30),
           burst_minutes: int = 20, cashout_share: float = 0.6, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = pd.to_datetime(df["TX_DATETIME"])
    first = t.min().normalize()
    last = t.max().normalize()
    start = first + pd.Timedelta(days=start_day)
    pool_terms = df["TERMINAL_ID"].unique()
    pool_custs = df["CUSTOMER_ID"].unique()
    compromised = rng.choice(pool_terms, size=terminals, replace=False)
    cust_mean = df.groupby("CUSTOMER_ID")["TX_AMOUNT"].mean()
    rows = []
    day = start
    while day <= last:
        for _ in range(bursts_per_day):
            term = rng.choice(compromised)
            t0 = day + pd.Timedelta(seconds=int(rng.integers(0, 86400 - burst_minutes * 60)))
            n = int(rng.integers(*burst_size))
            cards = rng.choice(pool_custs, size=n, replace=False)
            offs = np.sort(rng.uniform(0, burst_minutes * 60, n))
            for card, off in zip(cards, offs):
                when = t0 + pd.Timedelta(seconds=float(off))
                rows.append((when, int(card), int(term), round(float(rng.uniform(0.5, 9.99)), 2), TEST_SCENARIO))
                if rng.random() < cashout_share:
                    for _ in range(int(rng.integers(1, 3))):
                        later = when + pd.Timedelta(hours=float(rng.uniform(2, 72)))
                        if later.normalize() > last:
                            continue
                        base = float(cust_mean.get(card, 50.0))
                        amount = min(140.0, max(15.0, base * float(rng.uniform(0.9, 1.5))))
                        rows.append((later, int(card), int(rng.choice(pool_terms)), round(amount, 2), CASHOUT_SCENARIO))
        day += pd.Timedelta(days=1)
    new = pd.DataFrame(rows, columns=["TX_DATETIME", "CUSTOMER_ID", "TERMINAL_ID", "TX_AMOUNT", "TX_FRAUD_SCENARIO"])
    new["TX_FRAUD"] = 1
    if "TX_TIME_SECONDS" in df.columns:  # the handbook's own clock columns, continued
        new["TX_TIME_SECONDS"] = (new["TX_DATETIME"] - first).dt.total_seconds().astype("int64") + int(df["TX_TIME_SECONDS"].min() - (t.min() - first).total_seconds())
    if "TX_TIME_DAYS" in df.columns:
        new["TX_TIME_DAYS"] = (new["TX_DATETIME"] - first).dt.days + int(df["TX_TIME_DAYS"].min())
    new["TRANSACTION_ID"] = np.arange(len(new)) + int(df["TRANSACTION_ID"].max()) + 1
    new["TX_DATETIME"] = new["TX_DATETIME"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out = pd.concat([df, new[df.columns]], ignore_index=True)
    out = out.iloc[np.argsort(pd.to_datetime(out["TX_DATETIME"]).values, kind="stable")].reset_index(drop=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default=str(ROOT / "transactions.csv"))
    ap.add_argument("--out", default=str(ROOT / "transactions_drift.csv"))
    ap.add_argument("--start-day", type=int, default=128)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    df = pd.read_csv(a.src)
    out = inject(df, start_day=a.start_day, seed=a.seed)
    added = len(out) - len(df)
    new = out[out["TX_FRAUD_SCENARIO"].isin([TEST_SCENARIO, CASHOUT_SCENARIO])]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(a.out, index=False)
    print(f"inject_drift: added {added} payments from day {a.start_day} "
          f"({(new['TX_FRAUD_SCENARIO'] == TEST_SCENARIO).sum()} card tests, {(new['TX_FRAUD_SCENARIO'] == CASHOUT_SCENARIO).sum()} cash-outs, "
          f"${new['TX_AMOUNT'].sum():,.0f}) -> {a.out}")


if __name__ == "__main__":
    main()
