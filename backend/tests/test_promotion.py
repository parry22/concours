"""Model versions: v1 creation, promotion on a sufficient private gain, no promotion below the margin or on public-only gains."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models import ModelVersionRow, ProblemSpec, ProjectRow, SubmissionRow
from app.models_registry import promotion


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def project(s: Session, metric="recall_at_fpr", min_improvement=0.01) -> ProjectRow:
    spec = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, primary_metric=metric, metric_params={"fpr": 0.001} if metric == "recall_at_fpr" else {})
    row = ProjectRow(name="p", template="fraud", stage="protect", min_improvement=min_improvement)
    row.set_spec(spec)
    s.add(row)
    s.commit()
    s.refresh(row)
    return row


def scored(s: Session, pid: str, solver: str, public: float, private: float, t: int) -> SubmissionRow:
    sub = SubmissionRow(project_id=pid, solver=solver, status="scored", public_score=public, private_score=private,
                        created_at=datetime(2026, 1, 1, 0, 0, t, tzinfo=timezone.utc))
    s.add(sub)
    s.commit()
    s.refresh(sub)
    return sub


def test_should_promote_rule():
    assert promotion.should_promote(0.30, 0.303, min_improvement=0.01)
    assert not promotion.should_promote(0.30, 0.3029, min_improvement=0.01)
    assert not promotion.should_promote(0.30, None)
    assert promotion.should_promote(0.0, 0.01)
    # lower is better
    assert promotion.should_promote(0.20, 0.198, min_improvement=0.01, lower_is_better=True)
    assert not promotion.should_promote(0.20, 0.1981, min_improvement=0.01, lower_is_better=True)


def test_v1_is_the_best_baseline_solver_on_the_private_holdout(db):
    row = project(db)
    scored(db, row.id, "baseline_logreg", 0.227, 0.2156, 1)
    scored(db, row.id, "lgbm_default", 0.131, 0.139, 2)
    scored(db, row.id, "lgbm_tuned", 0.669, 0.3015, 3)  # not a baseline solver: never v1
    v1 = promotion.ensure_v1(db, row.id)
    assert v1 is not None and v1.version == 1 and v1.source == "baseline" and v1.solver_name == "baseline_logreg"
    assert v1.business_value.endswith(": 22%") and "false alarm" in v1.business_value
    db.refresh(row)
    assert row.active_model_id == v1.id and row.stage == "model"
    assert promotion.ensure_v1(db, row.id) is None  # idempotent


def test_promotion_on_sufficient_improvement(db):
    row = project(db)
    b = scored(db, row.id, "baseline_logreg", 0.227, 0.2156, 1)
    promotion.ensure_v1(db, row.id)
    cand = scored(db, row.id, "lgbm_tuned", 0.669, 0.3015, 2)
    v2 = promotion.consider(db, row.id, cand)
    assert v2 is not None and v2.version == 2 and v2.source == "local_contest" and v2.solver_name == "lgbm_tuned"
    versions = promotion.versions_for(db, row.id)
    assert [v.status for v in versions] == ["retired", "active"]
    out = promotion.versions_out(db, row.id, row.spec())
    assert out[1].improvement_line == "22% to 30% since your first model"
    assert out[0].improvement_line == "Your first model"
    assert promotion.consider(db, row.id, cand) is None  # the same submission is not promoted twice
    assert promotion.consider(db, row.id, b) is None  # v1's own submission never re-promotes


def test_no_promotion_below_threshold(db):
    row = project(db)
    scored(db, row.id, "baseline_logreg", 0.44, 0.4405, 1)
    promotion.ensure_v1(db, row.id)
    cand = scored(db, row.id, "lgbm_ensemble", 0.43, 0.4440, 2)  # +0.8%, under the 1% margin
    assert promotion.consider(db, row.id, cand) is None
    assert len(promotion.versions_for(db, row.id)) == 1


def test_no_promotion_on_public_only_gains(db):
    row = project(db)
    scored(db, row.id, "baseline_logreg", 0.227, 0.2156, 1)
    promotion.ensure_v1(db, row.id)
    better_public_worse_private = scored(db, row.id, "lgbm_default", 0.90, 0.139, 2)
    assert promotion.consider(db, row.id, better_public_worse_private) is None
    no_private = SubmissionRow(project_id=row.id, solver="agent_solver_1", status="scored", public_score=0.95, private_score=None)
    db.add(no_private)
    db.commit()
    assert promotion.consider(db, row.id, no_private) is None


def test_per_project_margin_and_after_run(db):
    row = project(db, min_improvement=0.005)
    a = scored(db, row.id, "baseline_logreg", 0.44, 0.4405, 1)
    b = scored(db, row.id, "lgbm_default", 0.41, 0.4300, 2)
    c = scored(db, row.id, "lgbm_regularized", 0.43, 0.4461, 3)
    d = scored(db, row.id, "lgbm_ensemble", 0.43, 0.4480, 4)  # +0.43% over c: below even the 0.5% margin
    made = promotion.after_run(db, row.id, [a.id, b.id, c.id, d.id])
    assert [v.version for v in made] == [1, 2]
    assert made[0].solver_name == "baseline_logreg" and made[1].solver_name == "lgbm_regularized"


def test_lower_is_better_direction(db):
    row = project(db, metric="wape")
    scored(db, row.id, "baseline_logreg", 0.31, 0.30, 1)
    promotion.ensure_v1(db, row.id)
    worse = scored(db, row.id, "lgbm_tuned", 0.2, 0.31, 2)
    assert promotion.consider(db, row.id, worse) is None
    better = scored(db, row.id, "lgbm_regularized", 0.2, 0.18, 3)
    v2 = promotion.consider(db, row.id, better)
    assert v2 is not None and v2.version == 2
