"""Post-outcome names: chargeback, refund, dispute, outcome, label, result, resolved, status, scenario.
Warn; the target_leak check upgrades to drop when the statistical test also fires."""
from __future__ import annotations

from app.models import Finding
from app.packager.checks.base import CheckContext

POST_OUTCOME_WORDS = ("chargeback", "refund", "dispute", "outcome", "label", "result", "resolved", "status", "scenario", "reason", "verdict")


def matches(name: str) -> str | None:
    l = name.lower()
    for w in POST_OUTCOME_WORDS:
        if w in l:
            return w
    return None


def run(ctx: CheckContext) -> None:
    for c in ctx.feature_columns:
        w = matches(c)
        if w:
            ctx.warn(
                Finding(
                    check="post_outcome_name",
                    severity="medium",
                    column=c,
                    reason=f"{c} is named like something recorded after the outcome is known (\"{w}\"). Check that it is available at prediction time.",
                    action="warned",
                    evidence={"word": w},
                )
            )
