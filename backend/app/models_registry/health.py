"""Performance watch. Score fresh labeled rows with the active version and compare with its holdout score."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.models import HealthOut, ModelVersionRow, ProblemSpec
from app.models_registry.lists import score_frame
from app.packager.protect import coerce_positive
from app.shared.metrics import LOWER_IS_BETTER, METRIC_NAMES, compute
from app.shared.translate import fmt_score, metric_label


def evaluate(project_id: str, version: ModelVersionRow, spec: ProblemSpec, df: pd.DataFrame, *, drift_threshold: float) -> HealthOut:
    if spec.target_column not in df.columns:
        raise ValueError(f"the file needs the outcome column {spec.target_column} so the model can be checked")
    positive = coerce_positive(df, spec.target_column, spec.positive_label)
    y = (df[spec.target_column] == positive).to_numpy().astype(int) if positive is not None else df[spec.target_column].to_numpy().astype(int)
    scores = score_frame(project_id, version, spec, df.drop(columns=[spec.target_column]))
    score = float(compute(spec.primary_metric, y, scores, spec.metric_params))
    ref = float(version.private_score)
    if spec.primary_metric in LOWER_IS_BETTER:
        drop = (score - ref) / abs(ref) if ref else 0.0
    else:
        drop = (ref - score) / abs(ref) if ref else 0.0
    health = "slipping" if drop > drift_threshold else "healthy"
    label = metric_label(spec)
    if health == "slipping":
        line = f"{label}: {fmt_score(spec, score)} on the new rows, down from {fmt_score(spec, ref)} when the model was built."
    else:
        line = f"{label}: {fmt_score(spec, score)} on the new rows, in line with {fmt_score(spec, ref)} when the model was built."
    return HealthOut(
        health=health,  # type: ignore[arg-type]
        model_version=version.version,
        rows=int(len(df)),
        positives=int(y.sum()),
        score=score,
        holdout_score=ref,
        drop=float(drop),
        threshold=drift_threshold,
        metric_name=METRIC_NAMES.get(spec.primary_metric, spec.primary_metric),
        line=line,
        checked_at=datetime.now(timezone.utc),
    )


def degrade(df: pd.DataFrame, target: str, *, seed: int = 0, share: float = 0.6) -> pd.DataFrame:
    """A deliberately worse sample for the demo and the tests: shuffle `share` of the labels."""
    rng = np.random.default_rng(seed)
    out = df.copy().reset_index(drop=True)
    idx = rng.choice(len(out), size=int(len(out) * share), replace=False)
    vals = out.loc[idx, target].to_numpy().copy()
    rng.shuffle(vals)
    out.loc[idx, target] = vals
    return out
