"""Leaderboard ordering, the 1% takeover rule, finalize."""
from __future__ import annotations

from app.config import TAKEOVER_MARGIN
from app.models import LeaderboardOut, ProblemSpec, SubmissionOut, SubmissionRow
from app.shared.translate import business_card, raw_metric_line, savings


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


def build(project_id: str, subs: list[SubmissionRow], spec: ProblemSpec, finalized: bool) -> LeaderboardOut:
    rows = rank(subs, finalized)
    leader = next((o for o in rows if o.is_leader), None)
    baseline = next((o for o in rows if o.solver == "baseline_logreg" and o.status == "scored"), None)
    card = raw = sav = formula = None
    if leader and baseline:
        b = baseline.private_score if finalized else baseline.public_score
        best = leader.private_score if finalized else leader.public_score
        if b is not None and best is not None:
            card = business_card(spec, b, best)
            raw = raw_metric_line(spec, b, best, finalized)
            sav, formula = savings(spec, b, best)
            for o in rows:
                sc = o.private_score if finalized else o.public_score
                if sc is not None:
                    o.business_value = business_card(spec, b, sc, short=True)
    return LeaderboardOut(project_id=project_id, finalized=finalized, submissions=rows, leader=leader, baseline=baseline,
                          business_card=card, raw_metric_line=raw, savings_line=sav, savings_formula=formula, takeover_margin=TAKEOVER_MARGIN)
