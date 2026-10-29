"""Deleting a project removes everything made from its data, not only the row and its folder: the rows that point
at it, its Docker images (which hold its training split and holdout), the fitted-model pickles and the arena cache
entries that only it used."""
from __future__ import annotations

import hashlib
import logging
import shutil

from sqlmodel import Session, delete, select

from app.config import ARENA_CACHE_DIR, SOLVERS_DIR, project_dir

log = logging.getLogger("concours.cleanup")


def purge_project(s: Session, project_id: str) -> dict:
    from app.arena import runner  # noqa: PLC0415
    from app.arena.stage import data_hash, solver_hash  # noqa: PLC0415
    from app.chain import ChainStateRow  # noqa: PLC0415
    from app.jobs import EventRow, JobRow  # noqa: PLC0415
    from app.models import CaseLabelRow, ListRow, ModelVersionRow, SubmissionRow  # noqa: PLC0415

    done: dict = {"rows": {}, "images": [], "cache": [], "pickles": []}
    # which cache keys belong to this project alone (a reseeded demo shares keys across projects)
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id)).all()
    keys = {sub.data_hash for sub in subs if sub.data_hash}
    shared = {k for k in keys if s.exec(select(SubmissionRow.id).where(SubmissionRow.data_hash == k, SubmissionRow.project_id != project_id)).first()}
    try:
        dh = data_hash(project_id)
    except OSError:
        dh = ""
    for table in (CaseLabelRow, ListRow, ModelVersionRow, SubmissionRow, JobRow, EventRow, ChainStateRow):
        n = s.exec(delete(table).where(table.project_id == project_id)).rowcount  # type: ignore[attr-defined]
        done["rows"][table.__tablename__] = n
    s.commit()
    for side in ("player", "referee"):
        try:
            runner.client().images.remove(runner.image_tag(project_id, side), force=True)
            done["images"].append(runner.image_tag(project_id, side))
        except Exception:  # noqa: BLE001  (no Docker, or no image)
            pass
    for k in keys - shared:
        key = k.replace(":", "-")
        for path in (ARENA_CACHE_DIR / f"{key}.json", ARENA_CACHE_DIR / key):
            if path.exists():
                shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True)
                done["cache"].append(str(path))
    if dh:
        serving = ARENA_CACHE_DIR.parent / "serving"
        for solver_dir in SOLVERS_DIR.iterdir():
            if not (solver_dir / "submission.py").exists():
                continue
            name = solver_dir.name
            key = hashlib.sha256(f"{name}:{solver_hash(name)}:{dh}".encode()).hexdigest()[:16]
            pkl = serving / f"{name}-{key}.pkl"
            if pkl.exists():
                pkl.unlink()
                done["pickles"].append(pkl.name)
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    log.info("purged project %s: %s", project_id, done)
    return done
