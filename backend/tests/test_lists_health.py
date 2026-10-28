"""Lists and the performance watch on the toy data: a list is ranked and cut at top_n; shuffled labels read as slipping."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app import config
from app.models import ModelVersionRow, ProblemSpec, ProjectRow
from app.models_registry import health, lists
from app.packager.protect import protect


@pytest.fixture
def toy_project(toy_df, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(config, "WORKSPACE_DIR", tmp_path)
    import app.models_registry.lists as L
    import app.serving.score as S
    import app.value.params as P

    for mod in (L, S, P):
        monkeypatch.setattr(mod, "project_dir", lambda pid, _t=tmp_path: (_t / pid).mkdir(parents=True, exist_ok=True) or (_t / pid))
    spec = ProblemSpec(template="custom", target_column="target", positive_label=1, time_column="event_time", primary_metric="recall_at_fpr", metric_params={"fpr": 0.05}, business_template="fraud")
    pid = "toy"
    protect(toy_df, spec, tmp_path / pid / "protected")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        row = ProjectRow(id=pid, name="toy", template="custom", stage="protect")
        row.set_spec(spec)
        s.add(row)
        v = ModelVersionRow(project_id=pid, version=1, source="baseline", solver_name="baseline_logreg", private_score=0.0, metric_name="r", business_value="x", status="active")
        s.add(v)
        s.commit()
        s.refresh(row)
        s.refresh(v)
        yield s, row, v, spec, tmp_path


def test_list_is_ranked_and_cut(toy_project):
    s, row, v, spec, tmp = toy_project
    hold = pd.read_csv(tmp / "toy" / "protected" / "holdout.csv")
    src = tmp / "new.csv"
    hold.to_csv(src, index=False)
    rec = lists.build(s, row, v, spec, src, top_n=25)
    out = lists.to_out(rec, "custom", spec)
    assert out.top_n == 25 and out.rows_scored == len(hold) and out.model_version == 1
    assert out.columns[:3] == ["rank", "score", "action"]
    full = pd.read_csv(rec.path)
    assert list(full["rank"]) == list(range(1, len(full) + 1))
    assert full["score"].is_monotonic_decreasing
    assert (full["action"].fillna("") != "").sum() == 25 and full["action"].iloc[0] == "Review"  # custom project with the fraud shape frames like fraud
    assert out.preview[0]["rank"] == 1 and len(out.preview) == 25
    assert row.stage == "model"


def test_health_flags_degraded_rows_as_slipping(toy_project):
    s, row, v, spec, tmp = toy_project
    hold = pd.read_csv(tmp / "toy" / "protected" / "holdout.csv")
    y = pd.read_csv(tmp / "toy" / "protected" / "holdout_labels.csv")["label"]
    labeled = hold.copy()
    labeled["target"] = y.to_numpy()
    # the reference is the model's own holdout score, so the clean sample must read as healthy
    v.private_score = health.evaluate("toy", v, spec, labeled, drift_threshold=0.10).score
    ok = health.evaluate("toy", v, spec, labeled, drift_threshold=0.10)
    assert ok.health == "healthy" and abs(ok.drop) < 1e-9 and "in line with" in ok.line
    bad = health.evaluate("toy", v, spec, health.degrade(labeled, "target", share=0.8), drift_threshold=0.10)
    assert bad.health == "slipping" and bad.drop > 0.10 and "down from" in bad.line


def test_health_needs_the_outcome_column(toy_project):
    s, row, v, spec, tmp = toy_project
    hold = pd.read_csv(tmp / "toy" / "protected" / "holdout.csv")
    with pytest.raises(ValueError):
        health.evaluate("toy", v, spec, hold, drift_threshold=0.1)
