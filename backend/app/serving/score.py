"""Fit a version's solver on the public train split (cached on disk) and score new rows. Lists and the performance
watch go through `fitted_model`; the module keeps the `brief_sub_` module prefix because cached pickles reference it.

Only the built-in solvers under backend/solvers/ are ever imported here. Code from outside (an agent-written attempt,
a chain miner's file) is scored through the player container instead (`scores_in_sandbox`), so it never runs with
the API's access to the data key, the ID map or the database."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import pickle
import sys
import threading
from pathlib import Path

import numpy as np
import pandas as pd

from app.arena.stage import data_hash, solver_hash
from app.config import ARENA_CACHE_DIR, SOLVERS_DIR, project_dir
from app.models import ProblemSpec
from app.packager.transform import Transform
from app.shared.csv_safe import safe_frame
from app.shared.metrics import threshold_at_fpr

BUILT_IN = frozenset(p.name for p in SOLVERS_DIR.iterdir() if (p / "submission.py").exists())


class OutsideCodeError(ValueError):
    """Code that did not ship with Concours (an agent attempt, a chain miner) is never imported on the host."""


def _load_solver_class(solver: str, submission_path: Path | None = None):
    if submission_path is not None or solver not in BUILT_IN:
        raise OutsideCodeError(f"{solver} is outside code: it is scored in the sandbox only")
    if str(SOLVERS_DIR) not in sys.path:
        sys.path.insert(0, str(SOLVERS_DIR))
    path = SOLVERS_DIR / solver / "submission.py"
    name = f"brief_sub_{solver}"
    if name in sys.modules:
        return sys.modules[name].Solver
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # registered so fitted models can be pickled and unpickled
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.Solver


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def fitted_model(project_id: str, solver: str, spec: ProblemSpec, submission_path: Path | None = None) -> tuple[object, float]:
    """Return (solver instance, threshold). Cached on disk per (solver code, data).
    `submission_path` is refused: outside code (agent attempts, chain miners) is scored by `scores_in_sandbox`."""
    protected = project_dir(project_id) / "protected"
    # next to the arena cache, outside workspace/: the same data and solver code reuse the fit after a reseed
    cache_dir = ARENA_CACHE_DIR.parent / "serving"
    cache_dir.mkdir(parents=True, exist_ok=True)
    code_hash = _file_hash(submission_path) if submission_path else solver_hash(solver)
    key = hashlib.sha256(f"{solver}:{code_hash}:{data_hash(project_id)}".encode()).hexdigest()[:16]
    cache = cache_dir / f"{solver}-{key}.pkl"
    solver_cls = _load_solver_class(solver, submission_path)
    if cache.exists():
        try:
            with open(cache, "rb") as f:
                return pickle.load(f)
        except (EOFError, pickle.UnpicklingError, AttributeError, ImportError):
            cache.unlink(missing_ok=True)
    transform = Transform.load(protected / "transform.json")
    train = pd.read_csv(protected / "train.csv")
    model = solver_cls(transform.model_dump())
    model.fit_frame(train)
    lb = pd.read_csv(protected / "leaderboard.csv")
    y_lb = pd.read_csv(protected / "leaderboard_labels.csv")["label"].to_numpy()
    s_lb = model.score_frame(lb)
    if spec.primary_metric == "recall_at_top_k":
        k = float(spec.metric_params.get("top_k", 0.10))
        thr = float(np.quantile(s_lb, 1 - k))
    else:
        thr = threshold_at_fpr(y_lb, s_lb, float(spec.metric_params.get("fpr", 0.001)))
    tmp = cache.with_name(f"{cache.name}.{os.getpid()}.{threading.get_ident()}.tmp")  # two requests may fit at once
    with open(tmp, "wb") as f:
        pickle.dump((model, thr), f)
    tmp.replace(cache)
    return model, thr


def code_path_for(project_id: str, version) -> Path | None:
    """Where a version's code lives when it is not a built-in solver: an agent attempt or a chain miner's file.
    None for the built-in solvers (which the host may import)."""
    from app.value.scores import submission_path  # noqa: PLC0415

    if version.solver_name in BUILT_IN:
        return None
    p = submission_path(project_id, version.solver_name)
    if p is not None:
        return p
    if version.submission_id:
        from app.db import session  # noqa: PLC0415
        from app.models import SubmissionRow  # noqa: PLC0415

        with session() as s:
            sub = s.get(SubmissionRow, version.submission_id)
            if sub is not None and sub.code_path:
                return Path(sub.code_path)
    raise OutsideCodeError(f"no code on disk for version {version.version} ({version.solver_name})")


def scores_in_sandbox(project_id: str, version, spec: ProblemSpec, feats: pd.DataFrame, code_path: Path) -> np.ndarray:
    """Score `feats` with outside code inside the player container (runner.score_rows). Cached per (code, rows)."""
    from app.arena import runner  # noqa: PLC0415
    from app.arena.stage import round_config  # noqa: PLC0415

    key = hashlib.sha256(code_path.read_bytes() + pd.util.hash_pandas_object(feats, index=False).to_numpy().tobytes()).hexdigest()[:16]
    cache_dir = project_dir(project_id) / "sandbox_scores"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{key}.csv"
    if cached.exists():
        return pd.read_csv(cached)["score"].to_numpy(dtype=float)
    rows = cache_dir / f"{key}.rows.csv"
    feats.to_csv(rows, index=False)
    out = runner.score_rows(project_id, key, code_path, rows, round_config(spec))
    scores = pd.read_csv(out)["score"].to_numpy(dtype=float)
    if len(scores) != len(feats):
        raise RuntimeError(f"sandbox returned {len(scores)} scores for {len(feats)} rows")
    pd.DataFrame({"score": scores}).to_csv(cached, index=False)
    rows.unlink(missing_ok=True)
    return scores


def score_csv(project_id: str, solver: str, spec: ProblemSpec, src: Path, dst: Path) -> dict:
    transform = Transform.load(project_dir(project_id) / "protected" / "transform.json")
    df = pd.read_csv(src, low_memory=False)
    feats = transform.apply(df)  # raises ValueError with the missing columns
    if transform.target_column in feats.columns:
        feats = feats.drop(columns=[transform.target_column])
    model, thr = fitted_model(project_id, solver, spec)
    scores = model.score_frame(feats)
    out = df.copy()
    out["score"] = np.round(scores, 6)
    out["flag"] = (scores >= thr).astype(int)
    safe_frame(out).to_csv(dst, index=False)
    preview = out.head(10).to_dict(orient="records")
    return {
        "rows": int(len(out)),
        "flagged": int(out["flag"].sum()),
        "threshold": float(thr),
        "solver": solver,
        "preview": [{k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()} for r in preview],
        "columns": list(out.columns),
    }
