"""Fit a version's solver on the public train split (cached on disk) and score new rows. Lists and the performance
watch go through `fitted_model`; the module keeps the `brief_sub_` module prefix because cached pickles reference it."""
from __future__ import annotations

import hashlib
import importlib.util
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.arena.stage import data_hash, solver_hash
from app.config import ARENA_CACHE_DIR, SOLVERS_DIR, project_dir
from app.models import ProblemSpec
from app.packager.transform import Transform
from app.shared.metrics import threshold_at_fpr


def _load_solver_class(solver: str, submission_path: Path | None = None):
    if str(SOLVERS_DIR) not in sys.path:
        sys.path.insert(0, str(SOLVERS_DIR))
    path = submission_path or (SOLVERS_DIR / solver / "submission.py")
    name = f"brief_sub_{solver}" + (f"_{_file_hash(path)}" if submission_path else "")
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
    `submission_path` points at code outside solvers/ (an agent-written attempt)."""
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
    tmp = cache.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump((model, thr), f)
    tmp.replace(cache)
    return model, thr


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
    out.to_csv(dst, index=False)
    preview = out.head(10).to_dict(orient="records")
    return {
        "rows": int(len(out)),
        "flagged": int(out["flag"].sum()),
        "threshold": float(thr),
        "solver": solver,
        "preview": [{k: (None if (isinstance(v, float) and np.isnan(v)) else v) for k, v in r.items()} for r in preview],
        "columns": list(out.columns),
    }
