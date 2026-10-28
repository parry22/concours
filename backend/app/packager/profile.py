"""Data profile: schema, column stats, masked sample rows. Only this (never raw data) reaches the LLM."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.models import ColumnProfile, DataProfile
from app.packager.pii import detect_pii_columns, mask_value

TIME_NAME_HINTS = ("date", "time", "timestamp", "datetime", "_at", "_ts")


def looks_like_time(series: pd.Series, name: str) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    lname = name.lower()
    if not any(h in lname for h in TIME_NAME_HINTS):
        return False
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        sample = series.dropna().astype(str).head(200)
        if sample.empty:
            return False
        try:
            parsed = pd.to_datetime(sample, errors="coerce")
        except (ValueError, TypeError):
            return False
        return bool(parsed.notna().mean() > 0.9)
    return False


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float):
        return None if math.isnan(v) or math.isinf(v) else round(v, 6)
    if isinstance(v, (int, str, bool)):
        return v
    if hasattr(v, "item"):
        try:
            return _jsonable(v.item())
        except (ValueError, TypeError):
            pass
    return str(v)


def _minmax(series: pd.Series) -> tuple[Any, Any]:
    s = series.dropna()
    if s.empty:
        return None, None
    if pd.api.types.is_numeric_dtype(s):
        return _jsonable(float(s.min())), _jsonable(float(s.max()))
    try:
        return _jsonable(str(s.min())), _jsonable(str(s.max()))
    except TypeError:
        return None, None


def _rows(df: pd.DataFrame, pii: set[str]) -> list[dict[str, Any]]:
    out = []
    for rec in df.to_dict(orient="records"):
        out.append({k: (mask_value(k, v) if k in pii else _jsonable(v)) for k, v in rec.items()})
    return out


def target_candidates(df: pd.DataFrame) -> list[str]:
    """Binary-looking columns, most likely targets first (name hints, then low cardinality)."""
    hints = ("fraud", "churn", "label", "target", "default", "is_", "flag", "outcome", "y")
    exact = ("y", "target", "label", "outcome", "churn", "fraud", "converted")
    cands = []
    for c in df.columns:
        s = df[c].dropna()
        if s.empty:
            continue
        nun = s.nunique()
        if nun == 2:
            l = c.lower()
            score = 3 if l in exact else 2 if any(h in l for h in hints) else 1
            cands.append((score, c))
    cands.sort(key=lambda t: -t[0])
    return [c for _, c in cands]


def profile_dataframe(
    df: pd.DataFrame, *, target: str | None = None, positive=None, sample_n: int = 20, preview_n: int = 10, seed: int = 42
) -> DataProfile:
    """`target` and `positive` (a template's known outcome column and label) make positive_rate exact; otherwise the
    rate is the rarer value of the most likely target candidate and is only a hint."""
    n = len(df)
    pii = set(detect_pii_columns(df))
    cols: list[ColumnProfile] = []
    for c in df.columns:
        s = df[c]
        nun = int(s.nunique(dropna=True))
        mn, mx = _minmax(s)
        cols.append(
            ColumnProfile(
                name=str(c),
                dtype=str(s.dtype),
                null_pct=round(float(s.isna().mean()) * 100, 3),
                unique_ratio=round(nun / n, 6) if n else 0.0,
                n_unique=nun,
                min=mn,
                max=mx,
                looks_like_time=looks_like_time(s, str(c)),
                pii_masked=c in pii,
            )
        )
    cands = target_candidates(df)
    pos_rate, rate_col = None, None
    if target and target in df.columns:
        t = df[target].dropna()
        rate_col = target
        if positive is not None:
            pos_rate = float((t.astype(str) == str(positive)).mean()) if len(t) else None
        else:
            counts = t.value_counts()
            pos_rate = float(counts.min() / counts.sum()) if len(counts) == 2 else None
    elif cands:
        t = df[cands[0]].dropna()
        rate_col = cands[0]
        # positive = the rarer value for a binary column
        counts = t.value_counts()
        pos_rate = float(counts.min() / counts.sum()) if len(counts) == 2 else None
    sample = df.sample(n=min(sample_n, n), random_state=seed) if n else df
    return DataProfile(
        n_rows=n,
        n_cols=len(df.columns),
        columns=cols,
        sample_rows=_rows(sample, pii),
        preview_rows=_rows(df.head(preview_n), pii),
        target_candidates=cands,
        positive_rate=pos_rate,
        positive_rate_column=rate_col,
    )


def read_csv(path, nrows: int | None = None) -> pd.DataFrame:
    return pd.read_csv(path, nrows=nrows, low_memory=False)
