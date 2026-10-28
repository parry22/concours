"""Per-row solver scores for the leaderboard and holdout splits.

Primary source: scores_<split>.csv written by the referee next to result.json. Fallback for runs that predate
that file: re-fit the solver locally through the serving path, then write the files so the next call is fast.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import ARENA_CACHE_DIR, project_dir
from app.models import ProblemSpec, SubmissionRow

log = logging.getLogger(__name__)
SPLITS = ("leaderboard", "holdout")


def labels(project_id: str, split: str) -> np.ndarray:
    return pd.read_csv(project_dir(project_id) / "protected" / f"{split}_labels.csv")["label"].to_numpy(dtype=np.int8)


def submission_path(project_id: str, solver: str) -> Path | None:
    """Where an agent-written submission lives; None for the built-in solvers."""
    m = re.fullmatch(r"agent_solver_(\d+)", solver)
    if not m:
        return None
    return project_dir(project_id) / "agent_solver" / f"attempt_{m.group(1)}" / "submission.py"


def _candidate_dirs(project_id: str, sub: SubmissionRow) -> list[Path]:
    dirs: list[Path] = []
    if sub.logs_path:
        dirs.append(Path(sub.logs_path) / "out")
    if sub.data_hash:
        dirs.append(ARENA_CACHE_DIR / sub.data_hash.replace(":", "-") / "out")
    dirs.append(project_dir(project_id) / "arena" / "value" / sub.id / "out")
    return dirs


def _read(d: Path) -> dict[str, np.ndarray] | None:
    files = {s: d / f"scores_{s}.csv" for s in SPLITS}
    if not all(f.exists() for f in files.values()):
        return None
    try:
        return {s: pd.read_csv(f)["score"].to_numpy(dtype=np.float64) for s, f in files.items()}
    except (ValueError, KeyError, OSError):
        return None


def _write(d: Path, scores: dict[str, np.ndarray]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for s, arr in scores.items():
        pd.DataFrame({"score": np.round(arr, 6)}).to_csv(d / f"scores_{s}.csv", index=False)


def _refit(project_id: str, sub: SubmissionRow, spec: ProblemSpec) -> dict[str, np.ndarray] | None:
    from app.serving.score import fitted_model  # noqa: PLC0415 - heavy import, only on the slow path

    path = submission_path(project_id, sub.solver)
    if path is not None and not path.exists():
        return None
    try:
        model, _ = fitted_model(project_id, sub.solver, spec, submission_path=path)
    except Exception as e:  # noqa: BLE001 - a solver that cannot be re-fit simply has no value report
        log.warning("value: re-fit of %s failed: %s", sub.solver, e)
        return None
    protected = project_dir(project_id) / "protected"
    out = {}
    for s in SPLITS:
        df = pd.read_csv(protected / f"{s}.csv")
        out[s] = np.asarray(model.score_frame(df), dtype=np.float64)
    return out


def split_scores(project_id: str, sub: SubmissionRow, spec: ProblemSpec, *, allow_refit: bool) -> dict[str, np.ndarray] | None:
    """Scores per split for a scored submission, or None when they are not on disk and re-fitting is not allowed."""
    if sub.status != "scored":
        return None
    dirs = _candidate_dirs(project_id, sub)
    for d in dirs:
        got = _read(d)
        if got and all(len(got[s]) == len(labels(project_id, s)) for s in SPLITS):
            return got
    if not allow_refit:
        return None
    got = _refit(project_id, sub, spec)
    if got is None:
        return None
    target = dirs[0] if sub.logs_path and Path(sub.logs_path).exists() else dirs[-1]
    try:
        _write(target, got)
    except OSError as e:
        log.warning("value: could not cache scores at %s: %s", target, e)
    return got
