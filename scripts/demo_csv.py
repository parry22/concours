"""Write the CSV uploaded live in the demo: a payments export as a fintech would hand it over.

Built from the fraud sample (data/templates/fraud/transactions.csv, six months of simulated card payments): about one
customer in thirty, every payment of theirs, renamed and dressed up so each step of the product has something to show.
The file stays under 10 MB: GitHub's port forwarding rejects larger uploads to the hosted copy with a 413.

- the mapping screen suggests every column by name (payment_id, created_at, amount_usd, customer_id, merchant_id,
  currency, is_fraud, vendor_risk_score);
- Protect removes card_number (Luhn-valid numbers, one per customer), scrambles customer and merchant IDs, handles
  customer_email as personal data, and drops chargeback_status, which is filled in only after the outcome is known;
- vendor_risk_score stands for the customer's current tool (a rule-like score on amount with some fraud signal), so
  Protect reports what that tool catches per day and every version is compared with it.

Usage: backend/.venv/bin/python scripts/demo_csv.py [out.csv] [--share 0.035]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "templates" / "fraud" / "transactions.csv"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = Path(args[0]) if args else ROOT / "demo-data" / "brightpay_payments_2018H1.csv"
SHARE = float(sys.argv[sys.argv.index("--share") + 1]) if "--share" in sys.argv else 0.035
rng = np.random.default_rng(31)


def luhn_card(body15: str) -> str:
    digits = [int(d) for d in body15]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            d -= 9 if d > 9 else 0
        total += d
    return body15 + str((10 - total % 10) % 10)


df = pd.read_csv(SRC)
customers = df["CUSTOMER_ID"].unique()
keep = rng.choice(customers, size=int(len(customers) * SHARE), replace=False)
df = df[df["CUSTOMER_ID"].isin(keep)].sort_values("TX_DATETIME").reset_index(drop=True)
y = df["TX_FRAUD"].to_numpy()

cards = {c: luhn_card("4" + "".join(map(str, rng.integers(0, 10, 14)))) for c in keep}
channel = rng.choice(["card_present", "online", "in_app"], size=len(df), p=[0.55, 0.3, 0.15])
# the current tool: big amounts look risky, and it catches about half the frauds a little better than chance
signal = 0.9 * np.log1p(df["TX_AMOUNT"].to_numpy()) + 1.4 * y * (rng.random(len(df)) < 0.5) + rng.normal(0, 1.0, len(df))
score = np.round(100 / (1 + np.exp(-(signal - 4.5))), 1)
status = np.where(y == 1, rng.choice(["chargeback_received", "confirmed_fraud"], size=len(df), p=[0.7, 0.3]), "none")

out = pd.DataFrame({
    "payment_id": [f"PAY-{i:07d}" for i in df["TRANSACTION_ID"]],
    "created_at": pd.to_datetime(df["TX_DATETIME"]).dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "amount_usd": df["TX_AMOUNT"].round(2),
    "currency": "USD",
    "customer_id": [f"CUS-{c:05d}" for c in df["CUSTOMER_ID"]],
    "customer_email": [f"customer{c}@example.com" for c in df["CUSTOMER_ID"]],
    "card_number": df["CUSTOMER_ID"].map(cards),
    "merchant_id": [f"MER-{t:05d}" for t in df["TERMINAL_ID"]],
    "channel": channel,
    "vendor_risk_score": score,
    "chargeback_status": status,
    "is_fraud": y,
})
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False)
t = pd.to_datetime(out["created_at"])
print(f"{OUT}: {len(out):,} payments, {out['customer_id'].nunique():,} customers, {out['merchant_id'].nunique():,} merchants, "
      f"{int(y.sum()):,} frauds ({y.mean():.2%}), {t.min():%Y-%m-%d} to {t.max():%Y-%m-%d}, {OUT.stat().st_size / 1e6:.1f} MB")
