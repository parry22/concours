"""Solvers train on the protected fraud train split and lgbm_tuned beats the baseline on holdout."""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.config import SOLVERS_DIR
from app.models import ProblemSpec
from app.packager.protect import protect
from app.shared import metrics


def load_solver(name: str):
    sys.path.insert(0, str(SOLVERS_DIR))
    spec = importlib.util.spec_from_file_location(f"sub_{name}", SOLVERS_DIR / name / "submission.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Solver


@pytest.mark.slow
def test_tuned_beats_baseline_on_fraud(fraud_df, tmp_path: Path):
    spec = ProblemSpec(template="fraud", target_column="TX_FRAUD", positive_label=1, time_column="TX_DATETIME")
    _, transform = protect(fraud_df, spec, tmp_path)
    train = pd.read_csv(tmp_path / "train.csv")
    hold = pd.read_csv(tmp_path / "holdout.csv")
    y = pd.read_csv(tmp_path / "holdout_labels.csv")["label"].to_numpy()
    scores = {}
    for name in ("baseline_logreg", "lgbm_tuned"):
        s = load_solver(name)(transform.model_dump())
        s.fit_frame(train)
        scores[name] = metrics.recall_at_fpr(y, s.score_frame(hold), 0.001)
    print(scores)
    assert scores["lgbm_tuned"] > scores["baseline_logreg"]
