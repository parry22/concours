"""Shared context for leakage and safety checks."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.models import Finding


@dataclass
class CheckContext:
    df: pd.DataFrame  # full dataset (before split)
    target: str
    positive: object
    time_column: str | None
    dropped: set[str] = field(default_factory=set)
    masked: set[str] = field(default_factory=set)
    findings: list[Finding] = field(default_factory=list)

    @property
    def feature_columns(self) -> list[str]:
        return [c for c in self.df.columns if c != self.target and c not in self.dropped]

    @property
    def y(self) -> pd.Series:
        return (self.df[self.target] == self.positive).astype(int)

    def drop(self, finding: Finding) -> None:
        if finding.column:
            self.dropped.add(finding.column)
        self.findings.append(finding)

    def warn(self, finding: Finding) -> None:
        self.findings.append(finding)


def time_derived(name: str, time_column: str | None) -> bool:
    """Sorted time and its derived seconds/days columns look monotonic; exclude them from ID checks."""
    if not time_column:
        return False
    if name == time_column:
        return True
    l = name.lower()
    return l.startswith("tx_time") or l.endswith(("_seconds", "_days", "_ts", "_epoch"))
