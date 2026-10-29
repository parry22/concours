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
from app.models import GateResult, ModelVersionOut, ModelVersionRow, ProblemSpec, ProjectRow, SubmissionRow
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
        created_at=v.created_at, gates=[GateResult(**g) for g in json.loads(v.gates_json)] if v.gates_json else [],
    )


def versions_out(s: Session, project_id: str, spec: ProblemSpec | None) -> list[ModelVersionOut]:
    rows = versions_for(s, project_id)
    v1 = next((v for v in rows if v.version == 1), None)
    out = [to_out(v, spec, v1) for v in rows]
    if spec and spec.primary_metric == "fraud_amount_per_day":
        for o, v in zip(out, rows):
            o.stats = _queue_stats(s.get(SubmissionRow, v.submission_id) if v.submission_id else None)
    for i, o in enumerate(out):
        o.changes = what_changed(o, out[i - 1] if i else None, spec)
    return out


SOURCE_LINES = {
    "baseline": "Your first model: the better of two simple models, trained on your payments and measured on days it never saw.",
    "local_contest": "Came from an improvement round run on this machine.",
    "apex_contest": "Came from the solver network.",
    "bittensor": "Written by an outside solver and submitted on chain; measured here like any attempt.",
    "apex_local": "Came from a run of the signed scorer images on this machine (not a live network run).",
    "apex_actions": "Came from a run of the signed scorer images on a GitHub Actions runner (not a live network run).",
}


def what_changed(v: ModelVersionOut, prev: ModelVersionOut | None, spec: ProblemSpec | None) -> list[str]:
    """Three to five sentences a fraud lead can read: where the version came from, what it gains over the one before,
    and which gates it passed. Every number comes from the stored scores and gate results."""
    lines = [SOURCE_LINES.get(v.source, "Promoted after a measured improvement.")]
    money = bool(spec and spec.primary_metric == "fraud_amount_per_day")
    if prev is not None:
        delta = v.private_score - prev.private_score
        rel = delta / prev.private_score if prev.private_score else None
        if money:
            lines.append(f"Catches ${delta:,.0f} more fraud per day than v{prev.version}" + (f" ({rel:+.0%})." if rel is not None else "."))
        elif rel is not None:
            lines.append(f"Measures {rel:+.1%} against v{prev.version} on the private holdout.")
        if v.stats and prev.stats:
            p_now, p_prev = v.stats.get("precision"), prev.stats.get("precision")
            if isinstance(p_now, (int, float)) and isinstance(p_prev, (int, float)) and abs(p_now - p_prev) >= 0.005:
                lines.append(f"Queue precision {'up' if p_now > p_prev else 'down'} from {p_prev:.1%} to {p_now:.1%}: "
                             f"{'more' if p_now > p_prev else 'fewer'} of the reviewed cases are fraud.")
    for g in v.gates:
        if g.key in ("luck", "segments", "speed") and g.passed and g.line:
            lines.append(g.line.rstrip(".") + ".")
    return lines[:5]


def _queue_stats(sub: SubmissionRow | None) -> dict:
    """The referee's holdout queue summary for a version (per-day arrays left out)."""
    if sub is None or not sub.result_json:
        return {}
    try:
        f = ((json.loads(sub.result_json).get("metadata") or {}).get("splits") or {}).get("holdout", {}).get("fraud") or {}
    except json.JSONDecodeError:
        return {}
    out = {k: v for k, v in f.items() if not isinstance(v, list)}
    days, caught = f.get("days") or [], f.get("caught_amount_by_day") or []
    out["daily"] = [{"day": d, "caught": c} for d, c in zip(days, caught)]  # the overview's per-day chart
    return out


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
    if spec.primary_metric == "fraud_amount_per_day":
        return _consider_fraud(s, row, active, sub, spec, source)
    if not should_promote(active.private_score, sub.private_score, min_improvement=row.min_improvement,
                          lower_is_better=spec.primary_metric in LOWER_IS_BETTER):
        return None
    return _new_version(s, row, spec, sub, source)


def _consider_fraud(s: Session, row: ProjectRow, active: ModelVersionRow, sub: SubmissionRow, spec: ProblemSpec, source: str) -> ModelVersionRow | None:
    """Fraud: the champion's re-score on a moved window refreshes the active version; anyone else must pass all five gates."""
    from app.fraud import promote as fp  # noqa: PLC0415
    from app.fraud.service import settings_of  # noqa: PLC0415

    active_sub = s.get(SubmissionRow, active.submission_id) if active.submission_id else None
    if sub.solver == active.solver_name:
        if fp.data_key(sub) != fp.data_key(active_sub):
            fp.refresh_champion(s, active, sub, spec)
        return None
    gates = fp.gates_for(s, row.id, sub, active, spec, settings_of(row))
    fp.store_gates(s, sub, gates)
    if not fp.passes(gates):
        return None
    v = _new_version(s, row, spec, sub, source)
    v.gates_json = sub.gates_json
    s.add(v)
    s.commit()
    s.refresh(v)
    return v


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
        v = consider(s, project_id, sub, source="bittensor" if sub.origin == "chain" else "local_contest")
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
