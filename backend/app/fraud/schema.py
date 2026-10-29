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
    "transaction_id": ["transactionid", "txid", "txnid", "transid", "paymentid", "orderid", "txnref", "txref", "transactionref", "paymentref",
                       "reference", "ref", "id"],
    "transaction_time": ["transactiontime", "txdatetime", "txtime", "timestamp", "datetime", "eventtime", "createdat", "postedat", "posted",
                         "created", "txdate", "txndate", "paymentdate", "transactiondate", "eventdate", "time", "date"],
    "amount": ["amount", "txamount", "txnamount", "txamt", "txnamt", "amountusd", "grossamount", "value", "amt", "total", "price"],
    "customer_id": ["customerid", "clientid", "userid", "accountid", "cardid", "cardholderid", "custid", "acctid", "customer", "cust", "client",
                    "user", "account", "acct", "cardholder"],
    "is_fraud": ["isfraud", "txfraud", "fraud", "fraudflag", "label", "target", "chargeback", "disputed", "dispute", "class"],
    "merchant_or_terminal_id": ["merchantid", "terminalid", "storeid", "merchant", "terminal", "shopid", "sellerid", "posid", "store", "shop", "seller", "pos"],
    "currency": ["currency", "currencycode", "ccy"],
    "label_time": ["labeltime", "fraudconfirmedat", "confirmedat", "chargebacktime", "chargebackdate", "reportedat", "labeldate"],
    "current_score": ["currentscore", "fraudscore", "riskscore", "vendorscore", "radarscore", "siftscore", "toolscore", "modelscore", "score", "risk"],
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
        if field == "transaction_time" and pick is None:
            dated = [c for c in cols if c not in used and _looks_like_time(df[c])]
            pick = dated[0] if len(dated) == 1 else None
        if pick is not None:
            used.add(pick)
        out[field] = pick
    return out


def _is_scenario(col: str) -> bool:
    # TX_FRAUD_SCENARIO is a fraud-named column but not the label
    return "scenario" in norm(col) or "type" in norm(col)


def _looks_like_time(s: pd.Series) -> bool:
    sample = s.dropna().astype(str).head(200)
    if sample.empty or pd.api.types.is_numeric_dtype(s):
        return False
    return parse_time(sample)[0].notna().mean() > 0.9


AMOUNT_JUNK = re.compile(r"[^\d.\-]")
EU_AMOUNT = re.compile(r"^\D*\d{1,3}(\.\d{3})+,\d{1,2}\D*$")
BLANKS = {"", "nan", "none", "null", "na", "n/a", "-"}


def parse_amount(s: pd.Series) -> pd.Series:
    """Numbers from a column that may carry currency symbols, spaces and thousands separators ($1,234.50, €87.38,
    1.234,50). Blanks become NaN."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").astype(float)
    txt = s.astype(str).str.strip()
    txt = txt.where(~txt.str.lower().isin(BLANKS), "")
    eu = txt.str.match(EU_AMOUNT)
    txt = txt.where(~eu, txt.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    cleaned = txt.str.replace(AMOUNT_JUNK, "", regex=True)
    return pd.to_numeric(cleaned.where(cleaned != "", None), errors="coerce").astype(float)


ISO_RE = r"^\d{4}-\d{2}-\d{2}"
SLASH_RE = r"^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"


def parse_time(s: pd.Series) -> tuple[pd.Series, list[str]]:
    """Datetimes from a column that may mix formats. ISO strings are read as such; day/month order in slash dates is
    decided from the values (any first number over 12 means day first). Returns the series and notes for the user."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s, []
    t = pd.to_datetime(s, errors="coerce")
    if t.notna().mean() >= 0.99:
        return _naive(t), []
    txt = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    notes: list[str] = []
    iso = txt.str.match(ISO_RE)
    slash = txt.str.match(SLASH_RE)
    other = ~(iso | slash) & (txt != "") & ~txt.str.lower().isin(BLANKS)
    if iso.any():
        out[iso] = _naive(pd.to_datetime(txt[iso], errors="coerce", format="ISO8601", utc=True))
    if slash.any():
        first = pd.to_numeric(txt[slash].str.extract(r"^(\d{1,2})")[0], errors="coerce")
        second = pd.to_numeric(txt[slash].str.extract(r"^\d{1,2}[/.-](\d{1,2})")[0], errors="coerce")
        dayfirst = bool((first > 12).any()) or not bool((second > 12).any())
        out[slash] = _naive(pd.to_datetime(txt[slash], errors="coerce", dayfirst=dayfirst, format="mixed", utc=True))
        notes.append(f"Dates with slashes were read as {'day/month/year' if dayfirst else 'month/day/year'}.")
    if other.any():
        out[other] = _naive(pd.to_datetime(txt[other], errors="coerce", format="mixed", utc=True))
    kinds = int(iso.any()) + int(slash.any()) + int(other.any())
    if kinds > 1:
        notes.insert(0, f"{kinds} date formats found in this column; all were read.")
    return out, notes


def _naive(t: pd.Series) -> pd.Series:
    try:
        return t.dt.tz_localize(None) if getattr(t.dt, "tz", None) is not None else t
    except (AttributeError, TypeError):
        return t


def _is_binary(s: pd.Series) -> bool:
    vals = {str(v).strip().lower() for v in s.dropna().unique()[:5]}
    return 0 < len(vals) <= 2 and vals <= (LABEL_TRUE | LABEL_FALSE)


def to_label(s: pd.Series) -> pd.Series:
    txt = s.astype(str).str.strip().str.lower()
    out = pd.Series(np.nan, index=s.index)
    out[txt.isin(LABEL_TRUE)] = 1
    out[txt.isin(LABEL_FALSE)] = 0
    return out


def _blank(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).str.strip().str.lower().isin(BLANKS)


def _examples(s: pd.Series, mask: pd.Series, n: int = 3) -> str:
    vals = [str(v)[:24] for v in s[mask].dropna().astype(str).unique()[:n]]
    return f" Examples: {', '.join(vals)}." if vals else ""


def inspect_mapping(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[list[str], list[str], dict | None]:
    """Problems that block confirmation, notes about what will be read or left out, and the date range found."""
    problems: list[str] = []
    notes: list[str] = []
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
        return problems, notes, None
    from app.packager.pii import classify_pii  # noqa: PLC0415

    ccol = mapping["customer_id"]
    if classify_pii(df[ccol].head(2000), str(ccol)) == "card":
        problems.append(f"{ccol} looks like card numbers. Use a customer, account or card ID that is not the card number itself; "
                        "card numbers are never kept, not even scrambled.")
    tcol, acol = mapping["transaction_time"], mapping["amount"]
    t, tnotes = parse_time(df[tcol])
    t_blank = _blank(df[tcol])
    t_bad = t.isna() & ~t_blank
    if t_bad.mean() > 0.01:
        problems.append(f"{tcol} does not read as dates and times.{_examples(df[tcol], t_bad)}")
    notes += tnotes
    a = parse_amount(df[acol])
    a_blank = _blank(df[acol])
    a_bad = a.isna() & ~a_blank
    if a_bad.mean() > 0.01:
        problems.append(f"{acol} does not read as numbers.{_examples(df[acol], a_bad)}")
    left_out = int((t.isna() | a.isna()).sum())
    if a_blank.mean() > 0.2:
        problems.append(f"More than 20% of payments have no {acol}; check the file.")
    elif left_out:
        notes.append(f"{left_out:,} payments without an amount or a time will be left out.")
    lab = to_label(df[mapping["is_fraud"]])
    if lab.isna().mean() > 0.01:
        problems.append(f"{mapping['is_fraud']} should be 0 or 1 (or yes and no).{_examples(df[mapping['is_fraud']], lab.isna())}")
    elif lab.sum() == 0:
        problems.append(f"{mapping['is_fraud']} has no fraud cases.")
    lt = mapping.get("label_time")
    if lt and lt in df.columns and parse_time(df[lt])[0].notna().sum() == 0:
        problems.append(f"{lt} does not read as dates.")
    time_range = None
    if t.notna().any():
        first, last = t.min().normalize(), t.max().normalize()
        time_range = {"start": first.strftime("%Y-%m-%d"), "end": last.strftime("%Y-%m-%d"), "days": int((last - first).days) + 1}
    return problems, notes, time_range


def validate(df: pd.DataFrame, mapping: dict[str, str | None]) -> list[str]:
    return inspect_mapping(df, mapping)[0]


def schema_out(df: pd.DataFrame, mapping: dict[str, str | None] | None, confirmed: bool) -> SchemaOut:
    sug = suggest(df)
    current = mapping or sug
    fields = [SchemaField(name=f, required=f in FRAUD_REQUIRED, column=current.get(f), suggested=sug.get(f)) for f in FRAUD_REQUIRED + FRAUD_OPTIONAL]
    preview = df.head(5).astype(object).where(df.head(5).notna(), None).to_dict(orient="records")
    problems, notes, time_range = ([], [], None) if confirmed and df.empty else inspect_mapping(df, current)
    return SchemaOut(columns=[str(c) for c in df.columns], fields=fields, preview=preview, confirmed=confirmed,
                     problems=problems, notes=notes, time_range=time_range)


def simulate_label_time(t: pd.Series, y: pd.Series, *, seed: int = SPLIT_SEED, low: int = LABEL_DELAY_RANGE[0],
                        high: int = LABEL_DELAY_RANGE[1]) -> pd.Series:
    """label_time for frauds: transaction_time + U(low, high) days, seeded. Legitimate rows have none."""
    rng = np.random.default_rng(seed)
    delay = pd.to_timedelta(rng.uniform(low, high, len(t)), unit="D")
    return pd.Series(np.where(y.to_numpy() == 1, (t + delay).to_numpy(), np.datetime64("NaT")), index=t.index)


def canonical(df: pd.DataFrame, mapping: dict[str, str | None]) -> tuple[pd.DataFrame, bool]:
    """Rename to the schema, coerce types (currency symbols, thousands separators and mixed date formats are read; rows
    without a time or an amount are left out), sort by time, simulate label_time when missing.
    Returns the frame and whether label_time was simulated. Unmapped columns stay, under their own names."""
    rename = {col: field for field, col in mapping.items() if col}
    out = df.rename(columns=rename).copy()
    clash = [c for c in out.columns if list(out.columns).count(c) > 1]
    if clash:
        raise ValueError(f"columns would collide after mapping: {sorted(set(clash))}")
    out["transaction_time"], _ = parse_time(out["transaction_time"])
    out["amount"] = parse_amount(out["amount"])
    out = out.dropna(subset=["transaction_time", "amount"])
    if "current_score" in out.columns:
        out["current_score"] = parse_amount(out["current_score"])  # the customer's own score: a feature and a benchmark
    out["is_fraud"] = to_label(out["is_fraud"]).fillna(0).astype(int)
    out["transaction_id"] = out["transaction_id"].astype(str)
    out = out.sort_values("transaction_time", kind="stable").reset_index(drop=True)
    simulated = "label_time" not in out.columns or parse_time(out["label_time"])[0].notna().sum() == 0
    if simulated:
        out["label_time"] = simulate_label_time(out["transaction_time"], out["is_fraud"])
    else:
        out["label_time"], _ = parse_time(out["label_time"])
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
