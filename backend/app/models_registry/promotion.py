"""Model versions and the promotion rules.

- v1: after Protect, the baseline solvers (`config.BASELINE_SOLVERS`) run through the arena; the best private
  holdout score becomes version 1, source "baseline". That is "Your model", before any contest.
- Promotion: a scored submission becomes a new version when its private holdout score beats the active
  version's by at least `project.min_improvement` (relative). The old version is retired. Public leaderboard
  scores never promote anything.
- Every version carries its business line, computed here from code.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.config import BASELINE_SOLVERS, DEFAULT_MIN_IMPROVEMENT
from app.models import ModelVersionOut, ModelVersionRow, ProblemSpec, ProjectRow, SubmissionRow
from app.shared.metrics import LOWER_IS_BETTER, METRIC_NAMES
from app.shared.translate import headline, improvement_line
from app.shared.translate import result_short as _result_short
from app.templates import load_defaults

DEFAULT_LIST = {"name": "Action list", "top_n": 100, "row_label": "row", "action_label": "Act"}


def should_promote(
    active_private: float,
    candidate_private: float | None,
    *,
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT,
    lower_is_better: bool = False,
) -> bool:
    """The one rule. Only private holdout scores count; a missing private score never promotes."""
    if candidate_private is None:
        return False
    if lower_is_better:
        if active_private <= 0:
            return candidate_private < active_private
        return candidate_private <= active_private * (1 - min_improvement)
    if active_private <= 0:
        return candidate_private > active_private
    return candidate_private >= active_private * (1 + min_improvement)


def pick_v1(subs: list[SubmissionRow], spec: ProblemSpec) -> SubmissionRow | None:
    """Best scored baseline-solver submission by private holdout score; any scored submission if no baseline ran."""
    scored = [s for s in subs if s.status == "scored" and s.private_score is not None]
    pool = [s for s in scored if s.solver in BASELINE_SOLVERS] or scored
    if not pool:
        return None
    lower = spec.primary_metric in LOWER_IS_BETTER
    return min(pool, key=lambda s: s.private_score) if lower else max(pool, key=lambda s: s.private_score)


# ---------- registry ----------


def versions_for(s: Session, project_id: str) -> list[ModelVersionRow]:
    return list(s.exec(select(ModelVersionRow).where(ModelVersionRow.project_id == project_id).order_by(ModelVersionRow.version)).all())


def active_version(s: Session, project_id: str) -> ModelVersionRow | None:
    return next((v for v in versions_for(s, project_id) if v.status == "active"), None)


def to_out(v: ModelVersionRow, spec: ProblemSpec | None, v1: ModelVersionRow | None) -> ModelVersionOut:
    imp = improvement_line(spec, v1.private_score, v.private_score) if spec and v1 else None
    return ModelVersionOut(
        id=v.id, project_id=v.project_id, version=v.version, source=v.source,  # type: ignore[arg-type]
        solver_name=v.solver_name, submission_id=v.submission_id, private_score=v.private_score, public_score=v.public_score,
        metric_name=v.metric_name, business_value=v.business_value, improvement_line=imp, status=v.status,  # type: ignore[arg-type]
        created_at=v.created_at,
    )


def versions_out(s: Session, project_id: str, spec: ProblemSpec | None) -> list[ModelVersionOut]:
    rows = versions_for(s, project_id)
    v1 = next((v for v in rows if v.version == 1), None)
    return [to_out(v, spec, v1) for v in rows]


def _new_version(s: Session, row: ProjectRow, spec: ProblemSpec, sub: SubmissionRow, source: str) -> ModelVersionRow:
    existing = versions_for(s, row.id)
    for v in existing:
        if v.status == "active":
            v.status = "retired"
            s.add(v)
    v = ModelVersionRow(
        project_id=row.id,
        version=(max((x.version for x in existing), default=0) + 1),
        source=source,
        solver_name=sub.solver,
        submission_id=sub.id,
        private_score=float(sub.private_score or 0.0),
        public_score=sub.public_score,
        metric_name=METRIC_NAMES.get(spec.primary_metric, spec.primary_metric),
        business_value=headline(spec, float(sub.private_score or 0.0)),
    )
    s.add(v)
    row.active_model_id = v.id
    row.winner_solver = sub.solver
    row.health = "unknown"
    row.health_json = None
    row.updated_at = datetime.now(timezone.utc)
    if row.stage in ("upload", "intake", "protect"):
        row.stage = "model"
    s.add(row)
    s.commit()
    s.refresh(v)
    return v


def ensure_v1(s: Session, project_id: str) -> ModelVersionRow | None:
    """Create version 1 from the scored submissions if the project has no version yet."""
    row = s.get(ProjectRow, project_id)
    if row is None or active_version(s, project_id) is not None:
        return None
    spec = row.spec()
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
    best = pick_v1(list(subs), spec) if spec else None
    if best is None:
        return None
    return _new_version(s, row, spec, best, "baseline")


def consider(s: Session, project_id: str, sub: SubmissionRow, *, source: str = "local_contest") -> ModelVersionRow | None:
    """Promote `sub` if it beats the active version on the private holdout by the project's margin."""
    row = s.get(ProjectRow, project_id)
    active = active_version(s, project_id)
    if row is None or active is None or sub.status != "scored":
        return None
    if sub.id == active.submission_id:
        return None
    if s.exec(select(ModelVersionRow).where(ModelVersionRow.submission_id == sub.id)).first():
        return None
    spec = row.spec()
    if not spec:
        return None
    if not should_promote(active.private_score, sub.private_score, min_improvement=row.min_improvement,
                          lower_is_better=spec.primary_metric in LOWER_IS_BETTER):
        return None
    return _new_version(s, row, spec, sub, source)


def after_run(s: Session, project_id: str, submission_ids: list[str]) -> list[ModelVersionRow]:
    """At the end of an arena run: build v1 if missing, then consider the run's other submissions in order."""
    made: list[ModelVersionRow] = []
    v1 = ensure_v1(s, project_id)
    if v1:
        made.append(v1)
    for sid in submission_ids:
        sub = s.get(SubmissionRow, sid)
        if sub is None:
            continue
        v = consider(s, project_id, sub)
        if v:
            made.append(v)
    return made


# ---------- template framing used by lists and tables ----------


def list_framing(template: str | None, spec: ProblemSpec | None = None) -> dict:
    for name in (template, spec.business_template if spec else None):
        cfg = load_defaults(name) if name else None
        if cfg and cfg.get("list"):
            return {**DEFAULT_LIST, **cfg["list"]}
    return dict(DEFAULT_LIST)


def result_short(spec: ProblemSpec, v1: ModelVersionOut | None, active: ModelVersionOut) -> str:
    return _result_short(spec, v1.private_score if v1 else None, active.private_score)


def version_payload(v: ModelVersionRow, spec: ProblemSpec | None, v1: ModelVersionRow | None) -> dict:
    return json.loads(to_out(v, spec, v1).model_dump_json())
