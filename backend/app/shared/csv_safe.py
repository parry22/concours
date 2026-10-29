"""CSV cells that Excel would run as formulas. Analysts open every export in a spreadsheet, so any cell that starts
with =, +, -, @ or a control character is prefixed with a single quote (OWASP CSV injection guidance). Numbers are
left alone: only text cells can carry a formula."""
from __future__ import annotations

import pandas as pd

DANGEROUS = ("=", "+", "-", "@", "\t", "\r", "\n")


def safe_cell(v):
    if isinstance(v, str) and v and v[0] in DANGEROUS:
        return "'" + v
    return v


def safe_frame(df: pd.DataFrame) -> pd.DataFrame:
    """A copy with every text cell made safe. Column names too: a header can be a formula as well."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_object_dtype(out[c]) or pd.api.types.is_string_dtype(out[c]):
            out[c] = out[c].map(safe_cell)
    out.columns = [safe_cell(str(c)) for c in out.columns]
    return out
