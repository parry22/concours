"""Apex-compatible local run: the signed Apex images, run on this machine, scored like any attempt.

`scripts/apex_local_run.sh` verifies the two GHCR images with cosign, pulls them by digest and runs the referee
against a submission exactly as the arena does. Each run leaves `result.json` (and the referee's `scores_*.csv`)
in `workspace/<pid>/apex_local/<solver>/out/`. `import_result` turns one such folder into a scored SubmissionRow
with origin "apex_local", considers it for promotion through the five gates, and publishes the leaderboard, so the
Improve screen shows it like a round. The origin is what the UI labels "Apex-compatible local run"; nothing here
claims a live network run. `status()` reports whether the competition is live anywhere (CONCOURS_APEX_STATUS).

    .venv/bin/python -m app.arena.apex_local import <project_id> <solver> <run_dir>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from sqlmodel import select

from app.arena import events, leaderboard
from app.arena.stage import data_hash, solver_hash
from app.config import env
from app.db import session
from app.models import ProjectRow, SubmissionRow

ORIGIN = "apex_local"
ORIGIN_ACTIONS = "apex_actions"
# none: not filed or not activated; local: Apex-compatible local run only; testnet | mainnet: activated by Macrocosmos
MODES = ("none", "local", "testnet", "mainnet")


def status() -> dict:
    """What the UI may say about Apex. Only CONCOURS_APEX_STATUS=testnet|mainnet (set by hand after Macrocosmos
    activates the competition) produces a "live" label; everything else is a local run or nothing."""
    mode = env("APEX_STATUS", "local").strip().lower()
    if mode not in MODES:
        mode = "local"
    live = mode in ("testnet", "mainnet")
    return {
        "mode": mode,
        "live": live,
        "dashboard_url": env("APEX_DASHBOARD_URL", "") or None,
        "label": {"none": "Not on Apex", "local": "Apex-compatible local run", "testnet": "Live on Apex testnet", "mainnet": "Live on Apex"}[mode],
    }


router = APIRouter(tags=["apex"])


@router.get("/apex/status")
def apex_status() -> dict:
    return status()


def import_result(project_id: str, solver: str, run_dir: Path, *, origin: str = ORIGIN, digests: dict | None = None, log=print) -> SubmissionRow:
    """Record one finished run (run_dir/out/result.json) as a scored attempt and consider it for promotion.
    Idempotent: the same solver on the same data with the same origin is returned, not duplicated."""
    from app.arena.service import _emit_board, promote_after_score  # noqa: PLC0415

    from app.arena.runner import read_result  # noqa: PLC0415

    result = read_result(run_dir / "out")
    if "raw_scores" not in result:
        raise ValueError(f"{run_dir / 'out' / 'result.json'} has no raw_scores")
    md = result.get("metadata") or {}
    public, private = md.get("public_score"), float(result["raw_scores"][0])
    if md.get("primary_metric") == "fraud_lift_in_capacity":
        # Apex v0.2.0 scores lift; Concours's screens, gates and value model keep money per day
        splits = md.get("splits") or {}
        public = (splits.get("leaderboard", {}).get("fraud") or {}).get("amount_per_day", public)
        private = (splits.get("holdout", {}).get("fraud") or {}).get("amount_per_day", private)
        md["apex_lift"] = {"private": float(result["raw_scores"][0]), "public": md.get("public_score")}
    md["apex_local"] = {"origin": origin, "digests": digests or {}, "imported_at": datetime.now(timezone.utc).isoformat()}
    result["metadata"] = md
    with session() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            raise ValueError(f"no project {project_id}")
        spec = row.spec()
        key = f"{data_hash(project_id)}:{solver_hash(solver)}"
        existing = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.solver == solver,
                                                      SubmissionRow.origin == origin, SubmissionRow.data_hash == key,
                                                      SubmissionRow.status == "scored")).first()
        if existing is not None:
            log(f"{solver}: already imported as attempt {existing.id} (same data, same code)")
            return existing
        sec = md.get("secondary") or {}
        sub = SubmissionRow(project_id=project_id, solver=solver, status="scored", data_hash=key, logs_path=str(run_dir), origin=origin,
                            public_score=public, private_score=float(private),
                            secondary_public=sec.get("public"), secondary_private=sec.get("private"),
                            eval_seconds=round(float(md.get("eval_time_in_seconds") or 0.0), 1), result_json=json.dumps(result))
        if result.get("terminal_reason") == "player_error":
            sub.status, sub.error = "failed", (md.get("error") or "player error")[:500]
        s.add(sub)
        row.finalized = True
        row.updated_at = datetime.now(timezone.utc)
        s.add(row)
        s.commit()
        s.refresh(sub)
        sid, out = sub.id, leaderboard.to_out(sub, True)
    events.publish(project_id, "submission_scored", out.model_dump())
    log(f"{solver}: imported as attempt {sid}, private score {sub.private_score}")
    if sub.status == "scored":
        promote_after_score(project_id, sid, spec, source=origin)
    _emit_board(project_id, spec)
    events.publish(project_id, "run_complete", {"ids": [sid], "purpose": "contest", "origin": origin})
    return sub


def find_project(name: str) -> str | None:
    """The newest project with this name (project ids are random, so a reseed changes them; names stay)."""
    with session() as s:
        rows = s.exec(select(ProjectRow).where(ProjectRow.name == name)).all()
        rows = sorted(rows, key=lambda r: r.updated_at or datetime.min, reverse=True)
        return rows[0].id if rows else None


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "import":
        digests = json.loads(argv[4]) if len(argv) > 4 else None
        import_result(argv[1], argv[2], Path(argv[3]), digests=digests)
        return 0
    if len(argv) == 2 and argv[0] == "find":
        pid = find_project(argv[1])
        if pid is None:
            print(f"no project named {argv[1]!r}", file=sys.stderr)
            return 1
        print(pid)
        return 0
    print("usage: python -m app.arena.apex_local import <project_id> <solver> <run_dir> [digests_json] | find <project name>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
