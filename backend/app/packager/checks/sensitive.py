"""Sensitive attributes: sex, gender, race, ethnicity, age, marital status, religion, nationality. Set aside.

Found by column name, and for unnamed or oddly named columns by their values. A sensitive column is left out of
training so the model cannot rank people by it, and kept aside (never shown to solvers) so the fairness report
can compare hit rate and selection rate across its groups.
"""
from __future__ import annotations

import re

import pandas as pd

from app.models import Finding
from app.packager.checks.base import CheckContext

# token in the column name -> the trait it names
NAME_TOKENS: dict[str, str] = {
    "sex": "sex",
    "gender": "gender",
    "race": "race",
    "racial": "race",
    "ethnicity": "ethnicity",
    "ethnic": "ethnicity",
    "age": "age",
    "marital": "marital status",
    "marriage": "marital status",
    "married": "marital status",
    "religion": "religion",
    "religious": "religion",
    "faith": "religion",
    "nationality": "nationality",
    "citizenship": "nationality",
}

# lower-cased values (spaces and punctuation removed) -> trait; a column matches when nearly all its values do
VALUE_SETS: dict[str, set[str]] = {
    "gender": {"male", "female", "m", "f", "man", "woman", "men", "women", "nonbinary", "unknowninvalid", "other"},
    "race": {"white", "black", "asian", "caucasian", "africanamerican", "hispanic", "latino", "latina", "native",
             "nativeamerican", "pacificislander", "other", "mixed", "multiracial"},
    "marital status": {"married", "single", "divorced", "widowed", "separated", "unmarried", "together", "partnered", "other"},
    "religion": {"christian", "muslim", "hindu", "jewish", "buddhist", "sikh", "atheist", "catholic", "protestant",
                 "none", "other"},
}
# the generic fallbacks ("other", "none", "m", "f") alone do not make a column sensitive
WEAK = {"other", "none", "m", "f", "unknowninvalid"}
MIN_SHARE = 0.9

TRAIT_TEXT = {
    "sex": "a person's sex",
    "gender": "a person's gender",
    "race": "a person's race",
    "ethnicity": "a person's ethnicity",
    "age": "a person's age",
    "marital status": "a person's marital status",
    "religion": "a person's religion",
    "nationality": "a person's nationality",
}


def name_tokens(name: str) -> list[str]:
    """`MaritalStatus` -> marital, status; `Age Group` -> age, group; `PAY_AMT1` -> pay, amt."""
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(name))
    return [t for t in re.split(r"[^a-z]+", spaced.lower()) if t]


def trait_by_name(name: str) -> str | None:
    for t in name_tokens(name):
        if t in NAME_TOKENS:
            return NAME_TOKENS[t]
    return None


def trait_by_values(s: pd.Series) -> str | None:
    if pd.api.types.is_numeric_dtype(s):
        return None
    vals = s.dropna().astype(str).str.lower().str.replace(r"[^a-z]", "", regex=True)
    vals = vals[vals != ""]
    if vals.empty:
        return None
    counts = vals.value_counts()
    if len(counts) < 2 or len(counts) > 20:
        return None
    for trait, known in VALUE_SETS.items():
        hit = counts[counts.index.isin(known)]
        strong = hit[~hit.index.isin(WEAK)]
        if hit.sum() / counts.sum() >= MIN_SHARE and len(strong) >= 2:
            return trait
    return None


def detect(df: pd.DataFrame, exclude: set[str]) -> dict[str, tuple[str, str]]:
    """column -> (trait, how it was found: "name" or "values")."""
    out: dict[str, tuple[str, str]] = {}
    for c in df.columns:
        if c in exclude:
            continue
        trait = trait_by_name(c)
        if trait:
            out[c] = (trait, "name")
            continue
        trait = trait_by_values(df[c])
        if trait:
            out[c] = (trait, "values")
    return out


def run(ctx: CheckContext) -> None:
    exclude = {ctx.target, ctx.time_column} if ctx.time_column else {ctx.target}
    for c, (trait, how) in detect(ctx.df[ctx.feature_columns + [ctx.target]], exclude).items():
        ctx.set_aside(
            Finding(
                check="sensitive",
                severity="medium",
                column=c,
                reason=(
                    f"{c} describes {TRAIT_TEXT[trait]}. It is left out of training so the model cannot rank people by it, "
                    "and kept aside to check that the list treats every group fairly."
                ),
                action="set_aside",
                evidence={"trait": trait, "found_by": how, "groups": int(ctx.df[c].nunique(dropna=True))},
            )
        )
