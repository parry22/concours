"""PII: emails, phones, card numbers (Luhn), name-like columns. Hash or mask."""
from __future__ import annotations

from app.models import Finding
from app.packager.checks.base import CheckContext
from app.packager.pii import classify_pii

KIND_TEXT = {
    "email": "email addresses",
    "phone": "phone numbers",
    "card": "card numbers",
    "name": "personal names or contact details",
}


def run(ctx: CheckContext) -> None:
    for c in ctx.feature_columns:
        kind = classify_pii(ctx.df[c], c)
        if not kind:
            continue
        ctx.masked.add(c)
        ctx.warn(
            Finding(
                check="pii",
                severity="high",
                column=c,
                reason=f"{c} contains {KIND_TEXT[kind]}. Solvers never need real identities, so values are replaced by one-way hashes.",
                action="masked",
                evidence={"kind": kind},
            )
        )
