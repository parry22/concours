"""Arena orchestration: queue solvers, run them one at a time in a worker thread, cache, publish SSE events."""
from __future__ import annotations

import json
import threading
from pathlib import Path
import time
from datetime import datetime, timezone

from sqlmodel import select

from app.arena import events, leaderboard, runner
from app.arena.stage import data_hash, round_config, solver_hash, stage
import shutil

from app.config import ARENA_CACHE_DIR
from app.db import session
from app.models import ProblemSpec, ProjectRow, SubmissionRow

REPLAY_STAGGER_S = 1.5
_running: dict[str, threading.Thread] = {}


def _log(project_id: str, line: str) -> None:
    events.publish(project_id, "log", {"line": line})


def start_run(project_id: str, solvers: list[str], *, replay: bool = True, rebuild: bool = False) -> list[str]:
    """Create queued submissions and start the worker. Returns submission ids."""
    if (t := _running.get(project_id)) and t.is_alive():
        raise RuntimeError("a run is already in progress")
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
        dh = data_hash(project_id)
        ids = []
        for name in solvers:
            sub = SubmissionRow(project_id=project_id, solver=name, status="queued", data_hash=f"{dh}:{solver_hash(name)}", logs_path="")
            s.add(sub)
            s.commit()
            s.refresh(sub)
            ids.append(sub.id)
        row.finalized = False
        s.add(row)
        s.commit()
    t = threading.Thread(target=_worker, args=(project_id, ids, spec, replay, rebuild), daemon=True)
    _running[project_id] = t
    t.start()
    return ids


def _cached(s, project_id: str, sub: SubmissionRow) -> SubmissionRow | None:
    """A scored submission with identical protected data and solver code: same project first, then any project,
    then the on-disk cache that survives `make demo` wiping workspace/."""
    q = select(SubmissionRow).where(SubmissionRow.solver == sub.solver, SubmissionRow.status == "scored",
                                    SubmissionRow.data_hash == sub.data_hash, SubmissionRow.id != sub.id)
    hit = s.exec(q.where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at.desc())).first()
    if hit:
        return hit
    hit = s.exec(q.order_by(SubmissionRow.created_at.desc())).first()
    if hit:
        return hit
    f = ARENA_CACHE_DIR / f"{sub.data_hash.replace(':', '-')}.json"
    if f.exists():
        d = json.loads(f.read_text())
        return SubmissionRow(project_id="cache", solver=sub.solver, status="scored", data_hash=sub.data_hash, **{k: d.get(k) for k in
                             ("public_score", "private_score", "secondary_public", "secondary_private", "eval_seconds", "logs_path", "result_json")})
    return None


def _store_cache(sub: SubmissionRow) -> None:
    ARENA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = sub.data_hash.replace(":", "-")
    logs_src = Path(sub.logs_path) if sub.logs_path else None
    logs_dst = ARENA_CACHE_DIR / key
    if logs_src and logs_src.exists():
        shutil.copytree(logs_src, logs_dst, dirs_exist_ok=True)
    (ARENA_CACHE_DIR / f"{key}.json").write_text(json.dumps({
        "solver": sub.solver, "public_score": sub.public_score, "private_score": sub.private_score,
        "secondary_public": sub.secondary_public, "secondary_private": sub.secondary_private,
        "eval_seconds": sub.eval_seconds, "logs_path": str(logs_dst), "result_json": sub.result_json}))


def _emit_board(project_id: str, spec: ProblemSpec) -> None:
    with session() as s:
        row = s.get(ProjectRow, project_id)
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
        board = leaderboard.build(project_id, subs, spec, row.finalized, profile=row.profile(), protect=row.protect())
    events.publish(project_id, "leaderboard_updated", board.model_dump())


def _worker(project_id: str, ids: list[str], spec: ProblemSpec, replay: bool, rebuild: bool) -> None:
    log = lambda line: _log(project_id, line)  # noqa: E731
    try:
        with session() as s:
            need_build = rebuild or any(_cached(s, project_id, s.get(SubmissionRow, i)) is None for i in ids)
        if need_build and (rebuild or runner.image_id(project_id, "player") is None or runner.image_id(project_id, "referee") is None or rebuild):
            log("staging competition folder and building player and referee images")
            stage(project_id, spec)
            runner.build_images(project_id, log)
        config = round_config(spec)
        for sid in ids:
            with session() as s:
                sub = s.get(SubmissionRow, sid)
                sub.status = "running"
                s.add(sub)
                s.commit()
                solver = sub.solver
                cached = _cached(s, project_id, sub) if replay else None
                cached_vals = (cached.public_score, cached.private_score, cached.secondary_public, cached.secondary_private, cached.eval_seconds, cached.logs_path, cached.result_json) if cached else None
            events.publish(project_id, "submission_started", {"id": sid, "solver": solver, "cached": cached_vals is not None})
            if cached_vals:
                time.sleep(REPLAY_STAGGER_S)
                with session() as s:
                    sub = s.get(SubmissionRow, sid)
                    sub.public_score, sub.private_score, sub.secondary_public, sub.secondary_private, sub.eval_seconds, sub.logs_path, sub.result_json = cached_vals
                    sub.status = "scored"
                    s.add(sub)
                    s.commit()
                    out = leaderboard.to_out(sub, False)
                log(f"{solver}: replayed cached score (same data, same solver code)")
            else:
                log(f"{solver}: running in Docker ({runner.SOLVER_CPUS} CPUs, {runner.SOLVER_MEM}, {runner.SOLVER_TIMEOUT_S}s limit)")
                res = runner.run_submission(project_id, sid, solver, config)
                with session() as s:
                    sub = s.get(SubmissionRow, sid)
                    sub.logs_path = str(res.logs_dir)
                    sub.eval_seconds = round(res.seconds, 1)
                    if res.ok and res.result:
                        md = res.result.get("metadata", {})
                        sub.public_score = md.get("public_score")
                        sub.private_score = res.result["raw_scores"][0]
                        sec = md.get("secondary") or {}
                        sub.secondary_public, sub.secondary_private = sec.get("public"), sec.get("private")
                        sub.result_json = json.dumps(res.result)
                        sub.status = "scored"
                        if res.result.get("terminal_reason") == "player_error":
                            sub.status = "failed"
                            sub.error = md.get("error", "player error")
                        elif res.result.get("terminal_reason") == "scored_with_player_faults":
                            faults = sum(v.get("faulted_chunks", 0) for v in (md.get("splits") or {}).values())
                            sub.error = f"the solver crashed on {faults} scoring batches; those rows scored 0"
                    else:
                        sub.status = "failed"
                        sub.error = res.error
                    s.add(sub)
                    s.commit()
                    out = leaderboard.to_out(sub, False)
                    if sub.status == "scored":
                        _store_cache(sub)
                log(f"{solver}: {out.status} in {res.seconds:.0f}s" + (f" ({out.error})" if out.error else ""))
            events.publish(project_id, "submission_scored", out.model_dump())
            _emit_board(project_id, spec)
        events.publish(project_id, "run_complete", {"ids": ids})
    except Exception as e:  # noqa: BLE001
        log(f"arena error: {e}")
        with session() as s:
            for sid in ids:
                sub = s.get(SubmissionRow, sid)
                if sub.status in ("queued", "running"):
                    sub.status = "failed"
                    sub.error = str(e)[:500]
                    s.add(sub)
            s.commit()
        events.publish(project_id, "run_complete", {"ids": ids, "error": str(e)})


def finalize(project_id: str) -> None:
    if (t := _running.get(project_id)) and t.is_alive():
        raise RuntimeError("wait for the run to finish")
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id)).all()
        row.finalized = True
        board = leaderboard.build(project_id, subs, spec, True)
        row.winner_solver = board.leader.solver if board.leader else None
        if row.stage == "arena":
            row.stage = "serve"
        s.add(row)
        s.commit()
    events.publish(project_id, "finalized", board.model_dump())


def is_running(project_id: str) -> bool:
    t = _running.get(project_id)
    return bool(t and t.is_alive())
