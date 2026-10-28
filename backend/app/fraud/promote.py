"""Promotion for fraud projects: the five gates instead of the 1% margin.

The champion (the active version's solver) is re-scored at the start of a round when the window moved, so the
challenger is always compared with it on the same holdout rows. That re-score refreshes the active version's
numbers; it never creates a version.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from app.config import project_dir
from app.fraud.gates import all_passed, evaluate
from app.models import FraudSettings, GateResult, ModelVersionRow, ProblemSpec, SubmissionRow
from app.shared.translate import headline


def data_key(sub: SubmissionRow | None) -> str:
    return (sub.data_hash or "").split(":")[0] if sub else ""


def champion_submission(s: Session, project_id: str, active: ModelVersionRow, key: str) -> SubmissionRow | None:
    """The champion's scored submission on the window `key`, newest first."""
    own = s.get(SubmissionRow, active.submission_id) if active.submission_id else None
    if own and own.status == "scored" and data_key(own) == key:
        return own
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.solver == active.solver_name,
                                              SubmissionRow.status == "scored").order_by(SubmissionRow.created_at.desc())).all()
    return next((x for x in subs if data_key(x) == key), None)


def seconds_per_10k(sub: SubmissionRow) -> float | None:
    try:
        md = json.loads(sub.result_json or "{}").get("metadata") or {}
    except json.JSONDecodeError:
        return None
    v = md.get("seconds_per_10k")
    return float(v) if v is not None else None


def gates_for(s: Session, project_id: str, sub: SubmissionRow, active: ModelVersionRow, spec: ProblemSpec, st: FraudSettings) -> list[GateResult]:
    from app.value.scores import labels, split_scores  # noqa: PLC0415

    champ = champion_submission(s, project_id, active, data_key(sub))
    chal_scores = split_scores(project_id, sub, spec, allow_refit=False)
    champ_scores = split_scores(project_id, champ, spec, allow_refit=False) if champ else None
    meta = pd.read_csv(project_dir(project_id) / "protected" / "holdout_meta.csv")
    y = labels(project_id, "holdout")
    return evaluate(
        chal_scores["holdout"] if chal_scores else np.array([]),
        champ_scores["holdout"] if champ_scores else None,
        y, meta["amount"].to_numpy(), meta["day"].to_numpy(), meta["new_customer"].to_numpy(), st,
        champion_version=active.version, private_score=sub.private_score, seconds_per_10k=seconds_per_10k(sub),
    )


def store_gates(s: Session, sub: SubmissionRow, gates: list[GateResult]) -> None:
    sub.gates_json = json.dumps([g.model_dump() for g in gates])
    s.add(sub)
    s.commit()


def gates_of(raw: str | None) -> list[GateResult]:
    return [GateResult(**g) for g in json.loads(raw)] if raw else []


def refresh_champion(s: Session, active: ModelVersionRow, sub: SubmissionRow, spec: ProblemSpec) -> None:
    """The champion scored on a new window: its numbers on that window become the active version's numbers."""
    active.submission_id = sub.id
    active.private_score = float(sub.private_score or 0.0)
    active.public_score = sub.public_score
    active.business_value = headline(spec, active.private_score)
    s.add(active)
    s.commit()


def passes(gates: list[GateResult]) -> bool:
    return all_passed(gates)
