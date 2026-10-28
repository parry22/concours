"""Validate the generated package: apex-dev preflight, apex-dev screen, and Brief's local referee run."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlmodel import select

from app.config import BACKEND_DIR
from app.db import session
from app.models import SubmissionRow, ValidationStep

APEX_DEV = Path(sys.executable).parent / "apex-dev"


def _run(args: list[str], cwd: Path) -> tuple[int, str]:
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError as e:
        return 127, f"{e}"
    except subprocess.TimeoutExpired:
        return 124, "timed out"


def preflight(comp: Path) -> ValidationStep:
    code, out = _run([str(APEX_DEV), "preflight", "--spec", "spec.yaml", "--input", "fixtures/input.json", "--env", "stage"], comp)
    return ValidationStep(name="apex-dev preflight", status="pass" if code == 0 else "fail", log=out)


def screen(comp: Path) -> ValidationStep:
    code, out = _run([str(APEX_DEV), "screen", "--repo", "."], comp)
    return ValidationStep(name="apex-dev screen", status="pass" if code == 0 else "fail", log=out)


def local_run(project_id: str) -> ValidationStep:
    """apex-dev run is not implemented upstream (exits 3). Brief's arena ran the same referee/player contract."""
    with session() as s:
        subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at.desc())).all()
    scored = [x for x in subs if x.status == "scored" and x.result_json]
    if not scored:
        return ValidationStep(name="local referee run", status="not_run", log="No arena run yet. Run the arena to produce a result.json through the referee/player contract.")
    r = json.loads(scored[0].result_json)
    ok = isinstance(r.get("raw_scores"), list) and len(r["raw_scores"]) == 1 and r.get("terminal_reason", "").startswith("scored")
    log = f"{len(scored)} submissions scored through the referee. Latest ({scored[0].solver}): raw_scores={r.get('raw_scores')}, terminal_reason={r.get('terminal_reason')}, steps={r.get('steps')}. Logs: {scored[0].logs_path}"
    return ValidationStep(name="local referee run", status="pass" if ok else "fail", log=log)


def overall(steps: list[ValidationStep]) -> str:
    if any(s.status == "fail" for s in steps):
        return "fail"
    if all(s.status == "pass" for s in steps):
        return "pass"
    return "not_run"
