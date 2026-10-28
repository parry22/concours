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
    set_aside_cols: dict[str, str] = field(default_factory=dict)  # sensitive column -> trait, not trained on
    keep_aside: set[str] = field(default_factory=set)  # dropped columns the split still needs (group key)
    group_column: str | None = None

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

    def set_aside(self, finding: Finding) -> None:
        """Sensitive: out of the features like a drop, but kept for the fairness report."""
        if finding.column:
            self.dropped.add(finding.column)
            self.set_aside_cols[finding.column] = str(finding.evidence.get("trait", ""))
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
