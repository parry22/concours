"""Arena orchestration: queue solvers as a job, run them one at a time in the worker, cache, publish live events.

A run has a purpose: "baseline" builds version 1 right after Protect; "contest" is an improvement round whose
scored attempts are considered for promotion as they arrive (see models_registry.promotion)."""
from __future__ import annotations

import json
from pathlib import Path
import time
from datetime import datetime, timezone

from sqlmodel import select

from app import jobs
from app.arena import events, leaderboard, runner
from app.arena.stage import data_hash, round_config, solver_hash, stage
import shutil

from app.models_registry import promotion

from app.config import ARENA_CACHE_DIR
from app.db import session
from app.models import ProblemSpec, ProjectRow, SubmissionRow

REPLAY_STAGGER_S = 1.5


def _log(project_id: str, line: str) -> None:
    events.publish(project_id, "log", {"line": line})


def start_run(project_id: str, solvers: list[str], *, replay: bool = True, rebuild: bool = False, purpose: str = "contest") -> list[str]:
    """Create queued submissions and a job for the worker. Returns submission ids."""
    if jobs.busy(project_id):
        raise RuntimeError("a run is already in progress")
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
        dh = data_hash(project_id)
        solvers = with_champion(s, project_id, spec, dh, list(solvers)) if purpose == "contest" else list(solvers)
        ids = []
        for name in solvers:
            sub = _new_submission(s, project_id, name, dh)
            ids.append(sub.id)
        row.finalized = False
        s.add(row)
        s.commit()
    jobs.enqueue(project_id, "arena_run", {"ids": ids, "replay": replay, "rebuild": rebuild, "purpose": purpose})
    return ids


def _new_submission(s, project_id: str, name: str, dh: str) -> SubmissionRow:
    """A queued attempt for a built-in solver, or a re-run of a miner's code (the active version can be a miner's)."""
    miner = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.solver == name,
                                               SubmissionRow.origin == "chain")).first()
    if miner is not None:
        sub = SubmissionRow(project_id=project_id, solver=name, status="queued", data_hash=f"{dh}:{miner.code_sha[:16]}", logs_path="",
                            origin="chain", hotkey=miner.hotkey, uid=miner.uid, chain_block=miner.chain_block,
                            code_sha=miner.code_sha, code_path=miner.code_path)
    else:
        sub = SubmissionRow(project_id=project_id, solver=name, status="queued", data_hash=f"{dh}:{solver_hash(name)}", logs_path="")
    s.add(sub)
    s.commit()
    s.refresh(sub)
    return sub


def start_chain_run(project_id: str, sub_ids: list[str]) -> list[str]:
    """An improvement round for attempts miners committed on chain (rows already created by the chain intake).
    The active version runs first when the window moved, as in a local round."""
    if jobs.busy(project_id):
        raise RuntimeError("a run is already in progress")
    with session() as s:
        row = s.get(ProjectRow, project_id)
        dh = data_hash(project_id)
        champion = [x for x in with_champion(s, project_id, row.spec(), dh, []) if x]
        ids = [_new_submission(s, project_id, name, dh).id for name in champion] + list(sub_ids)
        row.finalized = False
        s.add(row)
        s.commit()
    jobs.enqueue(project_id, "arena_run", {"ids": ids, "replay": True, "rebuild": False, "purpose": "contest"})
    return ids


def run_job_payload(project_id: str, payload: dict) -> None:
    """Called by the worker for an `arena_run` job."""
    with session() as s:
        spec = s.get(ProjectRow, project_id).spec()
    _worker(project_id, payload["ids"], spec, payload.get("replay", True), payload.get("rebuild", False), payload.get("purpose", "contest"))


def with_champion(s, project_id: str, spec: ProblemSpec | None, dh: str, solvers: list[str]) -> list[str]:
    """Fraud: when the active version has no score on this window (the clock moved), its solver runs first so
    every challenger is compared with it on the same holdout rows."""
    if not spec or spec.primary_metric != "fraud_amount_per_day":
        return solvers
    from app.fraud.promote import champion_submission  # noqa: PLC0415

    active = promotion.active_version(s, project_id)
    if active is None or champion_submission(s, project_id, active, dh) is not None:
        return solvers
    return [active.solver_name] + [x for x in solvers if x != active.solver_name]


def _same_rule(sub: SubmissionRow, spec: ProblemSpec) -> bool:
    """The cached numbers embed the scoring rule they were computed under; a result scored under another rule
    (the same data, a different metric) is not a hit."""
    try:
        meta = json.loads(sub.result_json or "{}").get("metadata") or {}
    except json.JSONDecodeError:
        return False
    return (
        meta.get("primary_metric") == spec.primary_metric
        and (meta.get("metric_params") or {}) == (spec.metric_params or {})
        and meta.get("secondary_metric") == spec.secondary_metric
    )


def _cached(s, project_id: str, sub: SubmissionRow, spec: ProblemSpec) -> SubmissionRow | None:
    """A scored submission with identical protected data, solver code and scoring rule: same project first, then
    any project, then the on-disk cache that survives `make demo` wiping workspace/."""
    q = select(SubmissionRow).where(SubmissionRow.solver == sub.solver, SubmissionRow.status == "scored",
                                    SubmissionRow.data_hash == sub.data_hash, SubmissionRow.id != sub.id)
    for scoped in (q.where(SubmissionRow.project_id == project_id), q):
        for hit in s.exec(scoped.order_by(SubmissionRow.created_at.desc())).all():
            if _same_rule(hit, spec):
                return hit
    f = ARENA_CACHE_DIR / f"{sub.data_hash.replace(':', '-')}.json"
    if f.exists():
        d = json.loads(f.read_text())
        hit = SubmissionRow(project_id="cache", solver=sub.solver, status="scored", data_hash=sub.data_hash, **{k: d.get(k) for k in
                            ("public_score", "private_score", "secondary_public", "secondary_private", "eval_seconds", "logs_path", "result_json")})
        if _same_rule(hit, spec):
            return hit
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


def build_board(s, project_id: str, spec: ProblemSpec, row: ProjectRow):
    """The leaderboard with version 1 as the reference row."""
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
    v1 = next((v for v in promotion.versions_for(s, project_id) if v.version == 1), None)
    return leaderboard.build(project_id, subs, spec, row.finalized, profile=row.profile(), protect=row.protect(),
                             v1_submission_id=v1.submission_id if v1 else None, v1_solver=v1.solver_name if v1 else None)


def _emit_board(project_id: str, spec: ProblemSpec) -> None:
    with session() as s:
        row = s.get(ProjectRow, project_id)
        board = build_board(s, project_id, spec, row)
    events.publish(project_id, "leaderboard_updated", board.model_dump())


def _emit_versions(project_id: str, made: list, spec: ProblemSpec) -> None:
    """One event per new version so the UI can show the promotion moment."""
    with session() as s:
        versions = promotion.versions_for(s, project_id)
        v1 = next((v for v in versions if v.version == 1), None)
        for v in made:
            fresh = s.get(type(v), v.id)
            payload = promotion.version_payload(fresh, spec, v1)
            events.publish(project_id, "model_version" if fresh.version == 1 else "model_promoted", payload)


def promote_after_score(project_id: str, sub_id: str, spec: ProblemSpec, *, source: str = "local_contest") -> None:
    """Consider one scored submission for promotion (contest runs and agent attempts)."""
    with session() as s:
        sub = s.get(SubmissionRow, sub_id)
        made = [v for v in [promotion.consider(s, project_id, sub, source=source)] if v]
    if made:
        _log(project_id, f"new model v{made[0].version} promoted ({made[0].business_value})")
        _emit_versions(project_id, made, spec)


def _worker(project_id: str, ids: list[str], spec: ProblemSpec, replay: bool, rebuild: bool, purpose: str = "contest") -> None:
    log = lambda line: _log(project_id, line)  # noqa: E731
    try:
        with session() as s:
            need_build = rebuild or any(_cached(s, project_id, s.get(SubmissionRow, i), spec) is None for i in ids)
        dh = data_hash(project_id)
        if need_build and (rebuild or not runner.images_current(project_id, dh)):
            log("staging competition folder and building player and referee images")
            stage(project_id, spec)
            runner.build_images(project_id, log, data=dh)
        config = round_config(spec)
        for sid in ids:
            with session() as s:
                sub = s.get(SubmissionRow, sid)
                sub.status = "running"
                s.add(sub)
                s.commit()
                solver = sub.solver
                code_path = Path(sub.code_path) if sub.code_path else None
                origin = sub.origin or "local"
                cached = _cached(s, project_id, sub, spec) if replay else None
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
                res = runner.run_submission(project_id, sid, solver, config, submission_path=code_path)
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
            if purpose == "contest":
                promote_after_score(project_id, sid, spec, source="bittensor" if origin == "chain" else "local_contest")
            _emit_board(project_id, spec)
        with session() as s:
            made = promotion.after_run(s, project_id, ids)
            row = s.get(ProjectRow, project_id)
            row.finalized = True  # every attempt in this run has its private holdout score
            if purpose == "contest" and row.stage == "model":
                row.stage = "improve"
            row.updated_at = datetime.now(timezone.utc)
            s.add(row)
            s.commit()
        if made:
            for v in made:
                log(f"model v{v.version} {'ready' if v.version == 1 else 'promoted'}: {v.business_value}")
            _emit_versions(project_id, made, spec)
        _emit_board(project_id, spec)
        events.publish(project_id, "run_complete", {"ids": ids, "purpose": purpose})
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
        events.publish(project_id, "run_complete", {"ids": ids, "error": str(e), "purpose": purpose})


def finalize(project_id: str) -> None:
    """Kept for older clients: marks the round closed and makes sure the versions reflect every scored attempt."""
    if jobs.busy(project_id):
        raise RuntimeError("wait for the run to finish")
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
        made = promotion.after_run(s, project_id, [x.id for x in subs])
        row.finalized = True
        row.updated_at = datetime.now(timezone.utc)
        s.add(row)
        s.commit()
        board = build_board(s, project_id, spec, row)
    if made:
        _emit_versions(project_id, made, spec)
    events.publish(project_id, "finalized", board.model_dump())


def is_running(project_id: str) -> bool:
    return jobs.busy(project_id)
