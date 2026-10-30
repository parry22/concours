"""Improvement attempts: ordering, the 1% takeover rule for the leader badge, business value per attempt."""
from __future__ import annotations

import json

from app.config import TAKEOVER_MARGIN
from app.models import GateResult, DataProfile, LeaderboardOut, ProblemSpec, ProtectReport, SubmissionOut, SubmissionRow
from app.shared.translate import business_card, headline, raw_metric_line


def to_out(r: SubmissionRow, finalized: bool) -> SubmissionOut:
    return SubmissionOut(
        id=r.id,
        solver=r.solver,
        status=r.status,  # type: ignore[arg-type]
        public_score=r.public_score,
        private_score=r.private_score if finalized else None,
        secondary_public=r.secondary_public,
        secondary_private=r.secondary_private if finalized else None,
        logs_path=r.logs_path,
        error=r.error,
        eval_seconds=r.eval_seconds,
        gates=[GateResult(**g) for g in json.loads(r.gates_json)] if r.gates_json else [],
        origin=r.origin or "local",
        submitted_by=r.submitted_by,
        hotkey=r.hotkey,
        uid=r.uid,
        chain_block=r.chain_block,
    )


def rank(subs: list[SubmissionRow], finalized: bool, margin: float = TAKEOVER_MARGIN) -> list[SubmissionOut]:
    """Leader = first scored submission; a later one takes over only if it beats the leader by `margin` (relative).
    Rows are ordered by the score shown (public until finalize, private after)."""
    key = (lambda r: r.private_score) if finalized else (lambda r: r.public_score)
    scored = [r for r in subs if r.status == "scored" and key(r) is not None]
    leader = None
    for r in sorted(scored, key=lambda r: r.created_at):
        if leader is None or key(r) > key(leader) * (1 + margin) + (1e-12 if key(leader) == 0 else 0):
            leader = r
    ordered = sorted(scored, key=lambda r: -key(r)) + [r for r in subs if r not in scored]
    out = []
    for i, r in enumerate(ordered):
        o = to_out(r, finalized)
        o.rank = i + 1 if r in scored else None
        o.is_leader = leader is not None and r.id == leader.id
        out.append(o)
    return out


def build(
    project_id: str,
    subs: list[SubmissionRow],
    spec: ProblemSpec,
    finalized: bool,
    *,
    profile: DataProfile | None = None,
    protect: ProtectReport | None = None,
    v1_submission_id: str | None = None,
    v1_solver: str | None = None,
) -> LeaderboardOut:
    """Improvement attempts. The reference is version 1 (`v1_submission_id`), else the plain baseline solver. Every row
    carries its business value from the private holdout score: that is the number promotion is decided on."""
    from app.value import service as value  # noqa: PLC0415 - value imports rank() from here

    rows = rank(subs, finalized)
    leader = next((o for o in rows if o.is_leader), None)
    baseline = next((o for o in rows if o.id == v1_submission_id), None) if v1_submission_id else None
    if baseline is None:
        baseline = next((o for o in rows if o.solver == "baseline_logreg" and o.status == "scored"), None)
    card = raw = sav = formula = None
    by_id = {r.id: r for r in subs}
    for o in rows:
        sc = by_id[o.id].private_score if o.id in by_id else None
        if sc is not None:
            o.business_value = headline(spec, sc)
    if leader and baseline:
        b_row, l_row = by_id.get(baseline.id), by_id.get(leader.id)
        b = b_row.private_score if b_row else None
        best = l_row.private_score if l_row else None
        if b is not None and best is not None:
            card = business_card(spec, b, best)
            raw = raw_metric_line(spec, b, best, True)
            rep = value.report_for(project_id, spec, subs, None, finalized=finalized, profile=profile, protect=protect, allow_refit=False,
                                   baseline_solver=v1_solver or "baseline_logreg")
            sav, formula = value.summary_lines(rep)
    return LeaderboardOut(project_id=project_id, finalized=finalized, submissions=rows, leader=leader, baseline=baseline,
                          business_card=card, raw_metric_line=raw, savings_line=sav, savings_formula=formula, takeover_margin=TAKEOVER_MARGIN)
