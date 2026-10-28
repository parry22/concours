"""Download the template datasets into data/templates/<name>/dataset.csv.

Fraud: 31 daily pickles (2018-07-01..2018-07-31) from Fraud-Detection-Handbook/simulated-data-raw.
Churn: UCI dataset 563 (Iranian Churn), CC BY 4.0.
Leads: UCI dataset 222 (Bank Marketing, bank-full.csv), CC BY 4.0.
Payments: UCI dataset 350 (Default of Credit Card Clients), CC BY 4.0.
Readmissions: UCI dataset 296 (Diabetes 130-US Hospitals, diabetic_data.csv), CC BY 4.0.
Attrition (IBM HR Analytics, fictional) is not downloaded: see data/templates/attrition/SOURCE.md.
No GPL code from the handbook is used; only its published data files are read.
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data" / "templates"
FRAUD_BASE = "https://raw.githubusercontent.com/Fraud-Detection-Handbook/simulated-data-raw/main/data/"
CHURN_ZIP = "https://archive.ics.uci.edu/static/public/563/iranian+churn+dataset.zip"
LEADS_ZIP = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
PAYMENTS_CSV = "https://archive.ics.uci.edu/static/public/350/data.csv"
READMISSIONS_ZIP = "https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip"
# UCI 350 publishes X1..X23 and Y; these are the names in the original spreadsheet's header row
PAYMENTS_NAMES = ["LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
                  *[f"BILL_AMT{i}" for i in range(1, 7)], *[f"PAY_AMT{i}" for i in range(1, 7)]]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def fraud(start: date = date(2018, 7, 1), days: int = 31) -> Path:
    out = ROOT / "fraud" / "dataset.csv"
    if out.exists():
        print("fraud: exists", out)
        return out
    frames = []
    for i in range(days):
        d = start + timedelta(days=i)
        raw = fetch(f"{FRAUD_BASE}{d.isoformat()}.pkl")
        df = pd.read_pickle(io.BytesIO(raw))
        frames.append(df)
        print(f"fraud: {d} rows={len(df)}", file=sys.stderr)
    df = pd.concat(frames, ignore_index=True)
    for c in ["CUSTOMER_ID", "TERMINAL_ID", "TX_TIME_SECONDS", "TX_TIME_DAYS"]:
        df[c] = df[c].astype("int64")
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"fraud: wrote {len(df)} rows, fraud rate {df['TX_FRAUD'].mean():.4%}")
    return out


def fraud_transactions(start: date = date(2018, 4, 1), days: int = 183) -> Path:
    """The fraud sample: 183 days (2018-04-01..2018-09-30, every day the handbook publishes) of simulated
    transactions, columns as published. Long enough for late labels (7 to 60 days), a 30-day embargo, a
    leaderboard and a holdout window, and four weeks after the as-of date for the drift demo. Days are fetched in
    parallel; a shorter file from an earlier run is extended with the missing days."""
    from concurrent.futures import ThreadPoolExecutor

    out = ROOT / "fraud" / "transactions.csv"
    have = 0
    old = None
    if out.exists():
        old = pd.read_csv(out)
        have = pd.to_datetime(old["TX_DATETIME"]).dt.normalize().nunique()
        if have >= days:
            print("fraud transactions: exists", out)
            return out

    def one(i: int) -> pd.DataFrame:
        d = start + timedelta(days=i)
        return pd.read_pickle(io.BytesIO(fetch(f"{FRAUD_BASE}{d.isoformat()}.pkl")))

    with ThreadPoolExecutor(max_workers=8) as ex:
        frames = list(ex.map(one, range(have, days)))
    df = pd.concat(frames, ignore_index=True)
    for c in ["TRANSACTION_ID", "CUSTOMER_ID", "TERMINAL_ID", "TX_TIME_SECONDS", "TX_TIME_DAYS", "TX_FRAUD", "TX_FRAUD_SCENARIO"]:
        df[c] = df[c].astype("int64")
    df["TX_DATETIME"] = pd.to_datetime(df["TX_DATETIME"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    if old is not None:
        df = pd.concat([old, df[old.columns]], ignore_index=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"fraud transactions: wrote {len(df)} rows over {days} days, fraud rate {df['TX_FRAUD'].mean():.4%}")
    return out


def churn() -> Path:
    out = ROOT / "churn" / "dataset.csv"
    if out.exists():
        print("churn: exists", out)
        return out
    z = zipfile.ZipFile(io.BytesIO(fetch(CHURN_ZIP)))
    name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
    df = pd.read_csv(io.BytesIO(z.read(name)))
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"churn: wrote {len(df)} rows, churn rate {df['Churn'].mean():.4%}, cols={list(df.columns)}")
    return out


def leads() -> Path:
    """bank-full.csv as published (`;` separated), with `,` as the separator. It has month and day of month but no
    year, and the campaign's last months are a different regime (about a third of contacts convert against 6% at the
    start), so the template splits stratified rather than by time."""
    out = ROOT / "leads" / "dataset.csv"
    if out.exists():
        print("leads: exists", out)
        return out
    outer = zipfile.ZipFile(io.BytesIO(fetch(LEADS_ZIP)))
    inner = zipfile.ZipFile(io.BytesIO(outer.read("bank.zip")))
    df = pd.read_csv(io.BytesIO(inner.read("bank-full.csv")), sep=";")
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"leads: wrote {len(df)} rows, conversion rate {(df['y'] == 'yes').mean():.4%}, cols={list(df.columns)}")
    return out


def payments() -> Path:
    """UCI 350 as published, with the spreadsheet's column names restored and Y named `default_next_month`."""
    out = ROOT / "payments" / "dataset.csv"
    if out.exists():
        print("payments: exists", out)
        return out
    df = pd.read_csv(io.BytesIO(fetch(PAYMENTS_CSV)))
    df = df.rename(columns={**{f"X{i + 1}": n for i, n in enumerate(PAYMENTS_NAMES)}, "Y": "default_next_month"})
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"payments: wrote {len(df)} rows, default rate {df['default_next_month'].mean():.4%}")
    return out


def readmissions() -> Path:
    """diabetic_data.csv with `readmitted` binarized: `readmitted_30d` is yes for "<30", no for ">30" and "NO".
    "?" (the file's missing marker) becomes empty. Encounter and patient numbers are kept: Protect must see them."""
    out = ROOT / "readmissions" / "dataset.csv"
    if out.exists():
        print("readmissions: exists", out)
        return out
    z = zipfile.ZipFile(io.BytesIO(fetch(READMISSIONS_ZIP)))
    df = pd.read_csv(io.BytesIO(z.read("diabetic_data.csv")), na_values=["?"], low_memory=False)
    df["readmitted_30d"] = (df.pop("readmitted") == "<30").map({True: "yes", False: "no"})
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"readmissions: wrote {len(df)} rows, {df['patient_nbr'].nunique()} patients, 30-day rate {(df['readmitted_30d'] == 'yes').mean():.4%}")
    return out


if __name__ == "__main__":
    which = sys.argv[1:] or ["fraud", "churn", "leads", "payments", "readmissions"]
    if "fraud" in which:
        fraud()
        fraud_transactions()
    if "churn" in which:
        churn()
    if "leads" in which:
        leads()
    if "payments" in which:
        payments()
    if "readmissions" in which:
        readmissions()
