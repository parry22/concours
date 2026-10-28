"""Repeated entities: an identifier column whose values repeat (one patient, many visits). Group split.

A random split would put some of a patient's visits in training and others in the hidden test data, so the
model is partly tested on people it has already seen. The column is dropped as a feature and becomes the group
key: every row of one entity lands on the same side of the split. Time-based splits keep their time order.
"""
from __future__ import annotations

import pandas as pd

from app.models import Finding
from app.packager.checks.base import CheckContext, time_derived
from app.packager.checks.sensitive import name_tokens

ID_TOKENS = {"id", "nbr", "number", "no", "key", "uuid", "guid"}
# between these shares of distinct values the column names entities that recur: fewer is a category, more is a row ID
MIN_UNIQUE_RATIO = 0.2
MAX_UNIQUE_RATIO = 0.95
MIN_REPEAT_ROWS = 0.01  # at least 1% of rows belong to an entity seen more than once


def entity_word(column: str, words: dict[str, str] | None = None) -> str:
    if words and words.get("entity"):
        return words["entity"]
    toks = [t for t in name_tokens(column) if t not in ID_TOKENS]
    return toks[0] if toks else "record"


def candidates(df: pd.DataFrame, columns: list[str], time_column: str | None) -> list[tuple[str, float, float]]:
    """(column, unique ratio, share of rows whose entity repeats), best first."""
    n = len(df)
    out = []
    for c in columns:
        if time_derived(c, time_column) or not n:
            continue
        s = df[c]
        if pd.api.types.is_float_dtype(s) or not set(name_tokens(c)) & ID_TOKENS:
            continue
        counts = s.value_counts(dropna=True)
        ratio = len(counts) / n
        repeat_share = float(counts[counts > 1].sum()) / n
        if MIN_UNIQUE_RATIO <= ratio <= MAX_UNIQUE_RATIO and repeat_share >= MIN_REPEAT_ROWS:
            out.append((c, round(ratio, 4), round(repeat_share, 4)))
    return sorted(out, key=lambda t: -t[2])


def run(ctx: CheckContext, words: dict[str, str] | None = None) -> None:
    found = candidates(ctx.df, ctx.feature_columns, ctx.time_column)
    if not found:
        return
    col, ratio, repeat_share = found[0]
    entity = entity_word(col, words)
    by_time = bool(ctx.time_column and ctx.time_column in ctx.df.columns)
    ctx.group_column = None if by_time else col
    reason = (
        f"{col} identifies a {entity} seen many times. It is dropped as a feature; the split by time already keeps the test data in the future."
        if by_time
        else f"The same {entity} appears in training and test data, which would make scores look better than reality."
    )
    ctx.drop(
        Finding(
            check="repeated_entity",
            severity="medium" if by_time else "high",
            column=col,
            reason=reason,
            action="dropped" if by_time else "group_split",
            evidence={"entities": int(ctx.df[col].nunique()), "unique_ratio": ratio, "rows_in_repeats": repeat_share,
                      "split": "time" if by_time else "group"},
        )
    )
    if not by_time:
        ctx.keep_aside.add(col)  # still needed by the split, never written to the solver files
