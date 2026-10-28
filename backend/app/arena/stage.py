"""Stage the competition folder for a project: workspace/<pid>/competition/.

This folder is both the Docker build context for the local arena and the Apex package that apex_builder
completes (spec.yaml, fixtures, HANDOFF.md, release workflow) and handoff zips.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from app.config import PLAYER_DIR, REFEREE_DIR, SOLVERS_DIR, VENDOR_DIR, BACKEND_DIR, project_dir
from app.models import ProblemSpec

PLAYER_DATA = ("train.csv", "transform.json")
REFEREE_DATA = ("leaderboard.csv", "leaderboard_labels.csv", "holdout.csv", "holdout_labels.csv")
HIDDEN_FILES = ("holdout.csv", "holdout_labels.csv")  # excluded from the handoff zip


def competition_dir(project_id: str) -> Path:
    return project_dir(project_id) / "competition"


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def stage(project_id: str, spec: ProblemSpec, *, max_train_rows: int = 0) -> Path:
    comp = competition_dir(project_id)
    protected = project_dir(project_id) / "protected"
    comp.mkdir(parents=True, exist_ok=True)
    # player
    player = comp / "player"
    player.mkdir(exist_ok=True)
    shutil.copyfile(PLAYER_DIR / "Dockerfile", player / "Dockerfile")
    shutil.copyfile(PLAYER_DIR / "launch.py", player / "launch.py")
    _copytree(VENDOR_DIR / "gym_v1", player / "gym_v1")
    _copytree(SOLVERS_DIR / "common", player / "common")
    (player / "data").mkdir(exist_ok=True)
    for f in PLAYER_DATA:
        shutil.copyfile(protected / f, player / "data" / f)
    shutil.copyfile(SOLVERS_DIR / "baseline_logreg" / "submission.py", player / "submission.py")
    # referee
    referee = comp / "referee"
    referee.mkdir(exist_ok=True)
    shutil.copyfile(REFEREE_DIR / "Dockerfile", referee / "Dockerfile")
    shutil.copyfile(REFEREE_DIR / "referee.py", referee / "referee.py")
    shutil.copyfile(BACKEND_DIR / "app" / "shared" / "metrics.py", referee / "metrics.py")
    _copytree(VENDOR_DIR / "gym_v1", referee / "gym_v1")
    (referee / "data").mkdir(exist_ok=True)
    for f in REFEREE_DATA:
        shutil.copyfile(protected / f, referee / "data" / f)
    # round config = what the referee receives as CONFIG_JSON
    (comp / "fixtures").mkdir(exist_ok=True)
    (comp / "fixtures" / "input.json").write_text(json.dumps(round_config(spec, max_train_rows), indent=2))
    return comp


def round_config(spec: ProblemSpec, max_train_rows: int = 0) -> dict:
    return {
        "tasks": [
            {"task_name": "leaderboard", "split": "leaderboard"},
            {"task_name": "holdout", "split": "holdout"},
        ],
        "primary_metric": spec.primary_metric,
        "metric_params": spec.metric_params,
        "secondary_metric": spec.secondary_metric,
        "max_train_rows": max_train_rows,
        "reset_timeout_s": 900,
    }


def data_hash(project_id: str) -> str:
    """Hash of the protected artifacts; arena results are cached per (solver, data_hash)."""
    protected = project_dir(project_id) / "protected"
    h = hashlib.sha256()
    for f in sorted(PLAYER_DATA + REFEREE_DATA):
        p = protected / f
        if p.exists():
            h.update(f.encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()[:16]


def solver_hash(solver: str) -> str:
    files = sorted((SOLVERS_DIR / solver).glob("*.py")) + sorted((SOLVERS_DIR / "common").glob("*.py")) + [PLAYER_DIR / "launch.py"]
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return h.hexdigest()[:16]
