"""Background jobs and their events, both in the database so the API and the worker can be separate processes.

- `JobRow`: an improvement round (or a baseline run) waiting for or held by a worker. A worker claims one job at
  a time (Postgres: `FOR UPDATE SKIP LOCKED`; SQLite: a guarded update), beats a heartbeat while it runs, and
  marks it done or failed. A job whose heartbeat stopped (the worker died) is failed on the next worker start
  and its unfinished attempts with it, so nothing stays "running" forever.
- `EventRow`: what the UI's live stream shows (log lines, attempts scored, versions promoted). The SSE endpoint
  reads new rows by id. Old rows are pruned.

`CONCOURS_WORKER=inline` (default, local) runs a worker thread inside the API process; production runs
`python -m app.worker` as its own container with `CONCOURS_WORKER=external`.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select

from app.config import env

log = logging.getLogger("concours.jobs")
WORKER_MODE = env("WORKER", "inline")  # inline | external
HEARTBEAT_S = 10
STALE_S = 120
POLL_S = 1.0
EVENT_KEEP = timedelta(days=2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobRow(SQLModel, table=True):
    __tablename__ = "job"

    id: str = SQLField(default_factory=lambda: uuid.uuid4().hex[:12], primary_key=True)
    project_id: str = SQLField(index=True)
    kind: str = "arena_run"
    payload_json: str = "{}"
    status: str = SQLField(default="queued", index=True)  # queued | running | done | failed
    worker: str = ""
    error: str | None = None
    created_at: datetime = SQLField(default_factory=_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None


class EventRow(SQLModel, table=True):
    __tablename__ = "event"

    id: int | None = SQLField(default=None, primary_key=True)
    project_id: str = SQLField(index=True)
    event: str
    data: str = "{}"
    created_at: datetime = SQLField(default_factory=_now)


# ---------- events ----------


def publish(project_id: str, event: str, data: Any) -> None:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        s.add(EventRow(project_id=project_id, event=event, data=json.dumps(data, default=str)))
        s.commit()


def last_event_id(project_id: str) -> int:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        row = s.exec(select(EventRow.id).where(EventRow.project_id == project_id).order_by(EventRow.id.desc()).limit(1)).first()
        return int(row or 0)


def events_after(project_id: str, after: int, limit: int = 200) -> list[EventRow]:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        return list(s.exec(select(EventRow).where(EventRow.project_id == project_id, EventRow.id > after).order_by(EventRow.id).limit(limit)).all())


def prune_events() -> None:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        s.exec(text("DELETE FROM event WHERE created_at < :t").bindparams(t=_now() - EVENT_KEEP))
        s.commit()


# ---------- jobs ----------


def enqueue(project_id: str, kind: str, payload: dict) -> JobRow:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        j = JobRow(project_id=project_id, kind=kind, payload_json=json.dumps(payload))
        s.add(j)
        s.commit()
        s.refresh(j)
    if WORKER_MODE == "inline":
        ensure_inline_worker()
    return j


def busy(project_id: str) -> bool:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        return s.exec(select(JobRow.id).where(JobRow.project_id == project_id, JobRow.status.in_(["queued", "running"]))).first() is not None


def _claim(worker: str) -> JobRow | None:
    from app.db import IS_SQLITE, session  # noqa: PLC0415

    with session() as s:
        q = select(JobRow).where(JobRow.status == "queued").order_by(JobRow.created_at).limit(1)
        if not IS_SQLITE:
            q = q.with_for_update(skip_locked=True)
        job = s.exec(q).first()
        if job is None:
            return None
        if IS_SQLITE:  # guarded update: another worker may have taken it meanwhile
            n = s.exec(text("UPDATE job SET status='running', worker=:w, started_at=:t, heartbeat_at=:t WHERE id=:id AND status='queued'")
                       .bindparams(w=worker, t=_now(), id=job.id)).rowcount
            s.commit()
            if n != 1:
                return None
            s.refresh(job)
            return job
        job.status, job.worker, job.started_at, job.heartbeat_at = "running", worker, _now(), _now()
        s.add(job)
        s.commit()
        s.refresh(job)
        return job


def _finish(job_id: str, status: str, error: str | None = None) -> None:
    from app.db import session  # noqa: PLC0415

    with session() as s:
        job = s.get(JobRow, job_id)
        if job:
            job.status, job.error, job.finished_at = status, (error or None) and error[:2000], _now()
            s.add(job)
            s.commit()


def _beat(job_id: str, stop: threading.Event) -> None:
    from app.db import session  # noqa: PLC0415

    while not stop.wait(HEARTBEAT_S):
        try:
            with session() as s:
                s.exec(text("UPDATE job SET heartbeat_at=:t WHERE id=:id").bindparams(t=_now(), id=job_id))
                s.commit()
        except Exception:  # noqa: BLE001 - a missed beat is retried; the job keeps running
            log.warning("heartbeat failed for job %s", job_id)


def recover_stale() -> int:
    """Fail jobs whose worker stopped beating, and their attempts that never finished."""
    from app.db import session  # noqa: PLC0415
    from app.models import SubmissionRow  # noqa: PLC0415

    cutoff = _now() - timedelta(seconds=STALE_S)
    n = 0
    with session() as s:
        for job in s.exec(select(JobRow).where(JobRow.status == "running")).all():
            hb = job.heartbeat_at or job.started_at or job.created_at
            if (hb if hb.tzinfo else hb.replace(tzinfo=timezone.utc)) > cutoff:
                continue
            job.status, job.error, job.finished_at = "failed", "The worker stopped while this round ran. Start the round again.", _now()
            s.add(job)
            for sid in json.loads(job.payload_json).get("ids", []):
                sub = s.get(SubmissionRow, sid)
                if sub and sub.status in ("queued", "running"):
                    sub.status, sub.error = "failed", job.error
                    s.add(sub)
            n += 1
        s.commit()
    return n


def run_job(job: JobRow) -> None:
    if job.kind == "arena_run":
        from app.arena.service import run_job_payload  # noqa: PLC0415

        run_job_payload(job.project_id, json.loads(job.payload_json))
    else:
        raise ValueError(f"unknown job kind {job.kind}")


def work_forever(stop: threading.Event | None = None, *, name: str | None = None) -> None:
    """The worker loop: recover, then claim and run jobs one at a time."""
    worker = name or f"{socket.gethostname()}:{os.getpid()}"
    stop = stop or threading.Event()
    recovered = recover_stale()
    if recovered:
        log.warning("failed %d stale jobs left by a stopped worker", recovered)
    last_prune = 0.0
    while not stop.is_set():
        job = None
        try:
            job = _claim(worker)
        except Exception:  # noqa: BLE001 - the database may be restarting; try again shortly
            log.exception("could not claim a job")
        if job is None:
            if time.monotonic() - last_prune > 3600:
                try:
                    prune_events()
                    recover_stale()
                except Exception:  # noqa: BLE001
                    log.exception("housekeeping failed")
                last_prune = time.monotonic()
            stop.wait(POLL_S)
            continue
        beat_stop = threading.Event()
        threading.Thread(target=_beat, args=(job.id, beat_stop), daemon=True).start()
        log.info("job started", extra={"path": job.kind, "org": job.project_id})
        try:
            run_job(job)
            _finish(job.id, "done")
        except Exception as e:  # noqa: BLE001 - the job fails, the worker keeps serving
            log.exception("job %s failed", job.id)
            _finish(job.id, "failed", str(e))
        finally:
            beat_stop.set()


_inline: threading.Thread | None = None
_inline_lock = threading.Lock()


def ensure_inline_worker() -> None:
    global _inline
    with _inline_lock:
        if _inline is None or not _inline.is_alive():
            _inline = threading.Thread(target=work_forever, kwargs={"name": f"inline:{os.getpid()}"}, daemon=True)
            _inline.start()
