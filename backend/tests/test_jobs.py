"""The job queue and stored events: one claim per job, stale jobs recovered, events read in order."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import db, jobs
from app.models import SubmissionRow


@pytest.fixture
def eng(monkeypatch):
    from app import auth as _auth  # noqa: F401  (register tables)

    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    monkeypatch.setattr(db, "engine", e)
    monkeypatch.setattr(jobs, "WORKER_MODE", "external")  # no thread: the test claims by hand
    return e


def test_a_job_is_claimed_once(eng):
    j = jobs.enqueue("p1", "arena_run", {"ids": []})
    assert jobs.busy("p1") and not jobs.busy("p2")
    got = jobs._claim("w1")
    assert got is not None and got.id == j.id and got.status == "running" and got.worker == "w1"
    assert jobs._claim("w2") is None
    jobs._finish(j.id, "done")
    assert not jobs.busy("p1")


def test_stale_jobs_and_their_attempts_fail(eng):
    with Session(eng) as s:
        sub = SubmissionRow(project_id="p1", solver="lgbm_tuned", status="running")
        s.add(sub)
        s.commit()
        s.refresh(sub)
        sid = sub.id
    j = jobs.enqueue("p1", "arena_run", {"ids": [sid]})
    jobs._claim("w1")
    with Session(eng) as s:
        row = s.get(jobs.JobRow, j.id)
        row.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        s.add(row)
        s.commit()
    assert jobs.recover_stale() == 1
    with Session(eng) as s:
        assert s.get(jobs.JobRow, j.id).status == "failed"
        assert s.get(SubmissionRow, sid).status == "failed"
    assert not jobs.busy("p1")


def test_a_fresh_heartbeat_is_left_alone(eng):
    jobs.enqueue("p1", "arena_run", {"ids": []})
    jobs._claim("w1")
    assert jobs.recover_stale() == 0 and jobs.busy("p1")


def test_events_are_read_in_order_after_an_id(eng):
    start = jobs.last_event_id("p1")
    for i in range(3):
        jobs.publish("p1", "log", {"line": f"line {i}"})
    jobs.publish("p2", "log", {"line": "other project"})
    got = jobs.events_after("p1", start)
    assert [e.data for e in got] == ['{"line": "line 0"}', '{"line": "line 1"}', '{"line": "line 2"}']
    assert jobs.events_after("p1", got[-1].id) == []


def test_unknown_job_kind_fails_the_job_not_the_worker(eng):
    j = jobs.enqueue("p1", "nope", {})
    claimed = jobs._claim("w1")
    with pytest.raises(ValueError):
        jobs.run_job(claimed)
    jobs._finish(j.id, "failed", "unknown kind")
    with Session(eng) as s:
        assert s.get(jobs.JobRow, j.id).status == "failed"
