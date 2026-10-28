"""PII detection and masking. Emails, phones, card numbers (Luhn), name-like column names."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import pandas as pd

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
PHONE_RE = re.compile(r"^\+?[\d\s().-]{7,20}$")
NAME_COLS = ("first_name", "last_name", "full_name", "surname", "customer_name", "name", "email", "phone", "address", "ssn", "passport")
CARD_COL_HINTS = ("card", "pan", "account_number", "iban")


def luhn_ok(s: str) -> bool:
    digits = [int(ch) for ch in s if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _share(series: pd.Series, pred, n: int = 500) -> float:
    s = series.dropna().astype(str).head(n)
    if s.empty:
        return 0.0
    return float(s.map(pred).mean())


def classify_pii(series: pd.Series, name: str) -> str | None:
    """Return a PII kind ('email', 'phone', 'card', 'name') or None. Content patterns first, then column names."""
    lname = name.lower().strip()
    numeric = pd.api.types.is_numeric_dtype(series)
    if not numeric:
        if _share(series, lambda v: bool(EMAIL_RE.match(v))) > 0.8:
            return "email"
    # card numbers by content whatever the column is called: 13 to 19 digits passing the Luhn check
    # (a float column prints as "4111...0.0", so integers are checked as integers)
    if pd.api.types.is_float_dtype(series):
        series = series.dropna()
        series = series[series == series.round()].astype("int64") if len(series) else series
    if _share(series, lambda v: v.replace(" ", "").replace("-", "").isdigit() and luhn_ok(v)) > 0.8:
        return "card"
    if any(h in lname for h in ("phone", "mobile", "tel")) and _share(series, lambda v: bool(PHONE_RE.match(v))) > 0.8:
        return "phone"
    if not numeric and (lname in NAME_COLS or any(lname.endswith("_" + h) for h in NAME_COLS)):
        return "name"
    return None


def detect_pii_columns(df: pd.DataFrame) -> dict[str, str]:
    out = {}
    for c in df.columns:
        kind = classify_pii(df[c], str(c))
        if kind:
            out[str(c)] = kind
    return out


def mask_value(col: str, v: Any) -> Any:
    if v is None or (isinstance(v, float) and v != v):
        return None
    s = str(v)
    if "@" in s:
        local, _, dom = s.partition("@")
        return f"{local[:1]}***@{dom}"
    if s.replace(" ", "").replace("-", "").isdigit() and len(s) >= 12:
        return f"****{s[-4:]}"
    return "***"


def hash_value(v: Any, salt: str = "brief") -> Any:
    if v is None or (isinstance(v, float) and v != v):
        return None
    return hashlib.sha256(f"{salt}:{v}".encode()).hexdigest()[:16]
