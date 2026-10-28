"""The illustrative improvement plan (Launch screen) and the suggested contest reward (HANDOFF.md only).

Nothing here is a price list. The subscription is a flat illustrative figure; the success fee is a share of
the value the active version adds over v1 per month, from the value model when it can price both versions.
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import PlanOut, ProblemSpec, ProjectRow, SubmissionRow
from app.models_registry.promotion import versions_for
from app.shared.translate import improvement_rel
from app.value import service as value_service

SUBSCRIPTION_PER_MONTH = 2_500.0
SUCCESS_FEE_SHARE = 0.20
REWARD_SHARE_OF_ANNUAL_UPLIFT = 0.25
REWARD_FLOOR = 2_000.0
REWARD_ROUND = 500.0


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _uplift_vs_v1(s: Session, row: ProjectRow, spec: ProblemSpec) -> float | None:
    versions = versions_for(s, row.id)
    active = next((v for v in versions if v.status == "active"), None)
    v1 = next((v for v in versions if v.version == 1), None)
    if not active or not v1 or active.id == v1.id:
        return None
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == row.id).order_by(SubmissionRow.created_at)).all()
    rep = value_service.report_for(row.id, spec, list(subs), active.solver_name, finalized=True, profile=row.profile(), protect=row.protect(),
                                   allow_refit=False, baseline_solver=v1.solver_name)
    return rep.uplift_net if rep else None


def improvement_plan(s: Session, row: ProjectRow) -> PlanOut:
    spec = row.spec()
    versions = versions_for(s, row.id)
    active = next((v for v in versions if v.status == "active"), None)
    v1 = next((v for v in versions if v.version == 1), None)
    rel = improvement_rel(spec, v1.private_score, active.private_score) if spec and active and v1 else None
    uplift = _uplift_vs_v1(s, row, spec) if spec else None
    fee = max(0.0, uplift) * SUCCESS_FEE_SHARE if uplift is not None else None
    lines = [f"Subscription: {_money(SUBSCRIPTION_PER_MONTH)} a month, covers hosting the model, daily lists and the performance watch."]
    if rel is not None and fee is not None:
        lines.append(f"Success fee: {SUCCESS_FEE_SHARE:.0%} of the value gained over your first model, measured each month. "
                     f"Today that is {_money(fee)} a month on a {rel:+.0%} improvement.")
    elif rel is not None:
        lines.append(f"Success fee: {SUCCESS_FEE_SHARE:.0%} of the value gained over your first model, measured each month. "
                     f"The current version is {rel:+.0%} over v1; add your costs on the Improve screen to price it.")
    else:
        lines.append(f"Success fee: {SUCCESS_FEE_SHARE:.0%} of the value gained over your first model, measured each month. "
                     "Nothing is owed until a later version beats v1.")
    return PlanOut(subscription_per_month=SUBSCRIPTION_PER_MONTH, success_fee_share=SUCCESS_FEE_SHARE, improvement_rel=rel,
                   value_uplift_per_month=uplift, success_fee_per_month=fee, lines=lines)


def suggested_reward(s: Session, row: ProjectRow) -> float:
    """For Macrocosmos only: a share of the annual value a further improvement could add, floored and rounded."""
    spec = row.spec()
    uplift = _uplift_vs_v1(s, row, spec) if spec else None
    if uplift is None or uplift <= 0:
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == row.id).order_by(SubmissionRow.created_at)).all()
        rep = value_service.report_for(row.id, spec, list(subs), None, finalized=True, profile=row.profile(), protect=row.protect(), allow_refit=False) if spec else None
        base = max(0.0, rep.contract.net) * 0.10 if rep else 0.0  # a tenth of the current monthly net value
    else:
        base = uplift
    reward = base * 12 * REWARD_SHARE_OF_ANNUAL_UPLIFT
    return max(REWARD_FLOOR, round(reward / REWARD_ROUND) * REWARD_ROUND)
