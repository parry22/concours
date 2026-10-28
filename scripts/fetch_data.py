"""Download the template datasets into data/templates/<name>/dataset.csv.

Fraud: 31 daily pickles (2018-07-01..2018-07-31) from Fraud-Detection-Handbook/simulated-data-raw.
Churn: UCI dataset 563 (Iranian Churn), CC BY 4.0.
Leads: UCI dataset 222 (Bank Marketing, bank-full.csv), CC BY 4.0.
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


if __name__ == "__main__":
    which = sys.argv[1:] or ["fraud", "churn", "leads"]
    if "fraud" in which:
        fraud()
    if "churn" in which:
        churn()
    if "leads" in which:
        leads()
