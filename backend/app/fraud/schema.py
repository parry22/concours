"""Map the user's columns onto the fraud schema and write the canonical dataset.

Required: transaction_id, transaction_time, amount, customer_id, is_fraud.
Optional: merchant_or_terminal_id, currency, label_time. Every other column is kept as an extra feature.
Suggestions come from the column names (and, for the label, from a 0/1 or yes/no column).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from app.config import LABEL_DELAY_RANGE, SPLIT_SEED
from app.models import FRAUD_OPTIONAL, FRAUD_REQUIRED, SchemaField, SchemaOut

# canonical field -> name patterns (normalized: lower case, letters and digits only), best first
PATTERNS: dict[str, list[str]] = {
    "transaction_id": ["transactionid", "txid", "txnid", "transid", "paymentid", "orderid", "id"],
    "transaction_time": ["transactiontime", "txdatetime", "txtime", "timestamp", "datetime", "eventtime", "createdat", "time", "date"],
    "amount": ["amount", "txamount", "txnamount", "value", "amt", "total", "price"],
    "customer_id": ["customerid", "clientid", "userid", "accountid", "cardid", "cardholderid", "customer", "user", "account"],
    "is_fraud": ["isfraud", "txfraud", "fraud", "fraudflag", "label", "target", "chargeback", "class"],
    "merchant_or_terminal_id": ["merchantid", "terminalid", "storeid", "merchant", "terminal", "shopid", "sellerid", "posid", "store", "shop", "seller", "pos"],
    "currency": ["currency", "currencycode", "ccy"],
    "label_time": ["labeltime", "fraudconfirmedat", "confirmedat", "chargebacktime", "chargebackdate", "reportedat", "labeldate"],
}
LABEL_TRUE = {"1", "true", "yes", "y", "fraud", "t"}
LABEL_FALSE = {"0", "false", "no", "n", "legit", "genuine", "f", "notfraud"}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def suggest(df: pd.DataFrame) -> dict[str, str | None]:
    """Best column per field by name; each column is used at most once."""
    cols = list(df.columns)
    used: set[str] = set()
    out: dict[str, str | None] = {}
    for field in FRAUD_REQUIRED + FRAUD_OPTIONAL:
        pick = None
        for pat in PATTERNS[field]:
            exact = [c for c in cols if c not in used and norm(c) == pat]
            if exact:
                pick = exact[0]
                break
        if pick is None:
            for pat in PATTERNS[field]:
                if len(pat) < 4:
                    continue  # short patterns ("id", "amt") only match exactly
                part = [c for c in cols if c not in used and pat in norm(c) and not _is_scenario(c)]
                if part:
                    pick = part[0]
                    break
        if field == "is_fraud" and pick is None:
            binary = [c for c in cols if c not in used and _is_binary(df[c])]
            pick = binary[0] if len(binary) == 1 else None
        if pick is not None:
            used.add(pick)
        out[field] = pick
    return out


def _is_scenario(col: str) -> bool:
    # TX_FRAUD_SCENARIO is a fraud-named column but not the label
    return "scenario" in norm(col) or "type" in norm(col)


def _is_binary(s: pd.Series) -> bool:
    vals = {str(v).strip().lower() for v in s.dropna().unique()[:5]}
    return 0 < len(vals) <= 2 and vals <= (LABEL_TRUE | LABEL_FALSE)


def to_label(s: pd.Series) -> pd.Series:
    txt = s.astype(str).str.strip().str.lower()
    out = pd.Series(np.nan, index=s.index)
    out[txt.isin(LABEL_TRUE)] = 1
    out[txt.isin(LABEL_FALSE)] = 0
    return out


def validate(df: pd.DataFrame, mapping: dict[str, str | None]) -> list[str]:
    problems = []
    for field in FRAUD_REQUIRED:
        col = mapping.get(field)
        if not col:
            problems.append(f"Choose the column for {field.replace('_', ' ')}.")
        elif col not in df.columns:
            problems.append(f"{col} is not a column in the file.")
    picked = [c for c in mapping.values() if c]
    if len(picked) != len(set(picked)):
        problems.append("Each column can be used for one field only.")
    if problems:
        return problems
    t = pd.to_datetime(df[mapping["transaction_time"]], errors="coerce")
    if t.isna().mean() > 0.01:
        problems.append(f"{mapping['transaction_time']} does not read as dates and times.")
    a = pd.to_numeric(df[mapping["amount"]], errors="coerce")
    if a.isna().mean() > 0.01:
        problems.append(f"{mapping['amount']} does not read as numbers.")
    lab = to_label(df[mapping["is_fraud"]])
    if lab.isna().mean() > 0.01:
        problems.append(f"{mapping['is_fraud']} should be 0 or 1 (or yes and no).")
    elif lab.sum() == 0:
        problems.append(f"{mapping['is_fraud']} has no fraud cases.")
    lt = mapping.get("label_time")
    if lt and lt in df.columns and pd.to_datetime(df[lt], errors="coerce").notna().sum() == 0:
        problems.append(f"{lt} does not read as dates.")
    return problems


def schema_out(df: pd.DataFrame, mapping: dict[str, str | None] | None, confirmed: bool) -> SchemaOut:
    sug = suggest(df)
    current = mapping or sug
    fields = [SchemaField(name=f, required=f in FRAUD_REQUIRED, column=current.get(f), suggested=sug.get(f)) for f in FRAUD_REQUIRED + FRAUD_OPTIONAL]
    preview = df.head(5).astype(object).where(df.head(5).notna(), None).to_dict(orient="records")
    return SchemaOut(columns=[str(c) for c in df.columns], fields=fields, preview=preview, confirmed=confirmed,
                     problems=[] if confirmed and df.empty else validate(df, current))


def simulate_label_time(t: pd.Series, y: pd.Series, *, seed: int = SPLIT_SEED, low: int = LABEL_DELAY_RANGE[0],
                        high: int = LABEL_DELAY_RANGE[1]) -> pd.Series:
    """label_time for frauds: transaction_time + U(low, high) days, seeded. Legitimate rows have none."""
    rng = np.random.default_rng(seed)
    delay = pd.to_timedelta(rng.uniform(low, high, len(t)), unit="D")
    return pd.Series(np.where(y.to_numpy() == 1, (t + delay).to_numpy(), np.datetime64("NaT")), index=t.index)


def canonical(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, bool]:
    """Rename to the schema, coerce types, sort by time, simulate label_time when missing.
    Returns the frame and whether label_time was simulated. Unmapped columns stay, under their own names."""
    rename = {col: field for field, col in mapping.items() if col}
    out = df.rename(columns=rename).copy()
    clash = [c for c in out.columns if list(out.columns).count(c) > 1]
    if clash:
        raise ValueError(f"columns would collide after mapping: {sorted(set(clash))}")
    out["transaction_time"] = pd.to_datetime(out["transaction_time"], errors="coerce")
    out = out.dropna(subset=["transaction_time"])
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce").astype(float)
    out["is_fraud"] = to_label(out["is_fraud"]).fillna(0).astype(int)
    out["transaction_id"] = out["transaction_id"].astype(str)
    out = out.sort_values("transaction_time", kind="stable").reset_index(drop=True)
    simulated = "label_time" not in out.columns or pd.to_datetime(out["label_time"], errors="coerce").notna().sum() == 0
    if simulated:
        out["label_time"] = simulate_label_time(out["transaction_time"], out["is_fraud"])
    else:
        out["label_time"] = pd.to_datetime(out["label_time"], errors="coerce")
        # a fraud without a confirmation date is taken as confirmed at the transaction (known at once)
        missing = (out["is_fraud"] == 1) & out["label_time"].isna()
        out.loc[missing, "label_time"] = out.loc[missing, "transaction_time"]
    return out, simulated


def write_canonical(df: pd.DataFrame, path) -> None:
    """Encrypted at rest: it still holds the real customer and merchant IDs."""
    from app import secure_store  # noqa: PLC0415

    secure_store.to_csv(df, path, date_format="%Y-%m-%d %H:%M:%S")


def drop_card_columns(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, list[str]]:
    """Columns holding card numbers (Luhn) never reach disk: removed before the canonical dataset is written."""
    from app.packager.pii import classify_pii  # noqa: PLC0415

    mapped = {c for c in mapping.values() if c}
    cards = [c for c in df.columns if c not in mapped and classify_pii(df[c].head(2000), str(c)) == "card"]
    return df.drop(columns=cards), cards


def profile(df: pd.DataFrame, *, target: str | None, positive=None, sample: int = 100_000):
    """The upload profile from a seeded sample (column stats, preview), with the row count and the fraud rate from
    every row: profiling 1.7M payments in full takes tens of seconds and changes nothing on screen."""
    from app.packager.profile import profile_dataframe  # noqa: PLC0415

    part = df.sample(n=sample, random_state=42).sort_index() if len(df) > sample else df
    prof = profile_dataframe(part, target=target, positive=positive)
    update = {"n_rows": len(df)}
    if target and target in df.columns and positive is not None:
        update["positive_rate"] = float((to_label(df[target]) == 1).mean()) if df[target].dtype == object else float((df[target] == positive).mean())
    return prof.model_copy(update=update)


def read_canonical(path) -> pd.DataFrame:
    from app import secure_store  # noqa: PLC0415

    df = secure_store.read_csv(path, low_memory=False, dtype={"transaction_id": str})
    df["transaction_time"] = pd.to_datetime(df["transaction_time"])
    df["label_time"] = pd.to_datetime(df["label_time"], errors="coerce")
    return df
