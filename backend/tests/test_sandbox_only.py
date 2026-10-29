"""Outside code (agent attempts, chain miners) never runs on the host: serving refuses it, reasons work without a model."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.fraud.reasons import explain_plain
from app.models import ProblemSpec
from app.serving.score import BUILT_IN, OutsideCodeError, _load_solver_class, fitted_model


def test_built_in_solvers_are_the_only_importable_code(tmp_path: Path):
    assert "baseline_logreg" in BUILT_IN and "lgbm_tuned" in BUILT_IN
    outside = tmp_path / "submission.py"
    outside.write_text("import os\nclass Solver:\n    pass\n")
    with pytest.raises(OutsideCodeError):
        _load_solver_class("baseline_logreg", submission_path=outside)
    with pytest.raises(OutsideCodeError):
        _load_solver_class("agent_solver_1")
    with pytest.raises(OutsideCodeError):
        _load_solver_class("miner-abcdef12-01234567")
    spec = ProblemSpec(target_column="is_fraud", positive_label=1, primary_metric="fraud_amount_per_day", metric_params={})
    with pytest.raises(OutsideCodeError):
        fitted_model("p", "agent_solver_2", spec, submission_path=outside)


def test_plain_reasons_without_a_model():
    t = pd.date_range("2024-01-01 23:00", periods=6, freq="h")
    frame = pd.DataFrame({"transaction_time": t, "amount": [5.0, 5.0, 5.0, 5.0, 900.0, 5.0],
                          "customer_id": [1, 1, 1, 1, 2, 3], "merchant_or_terminal_id": [7] * 6})
    scores = np.array([0.1, 0.1, 0.1, 0.1, 0.9, 0.2])
    why = explain_plain(frame, scores, np.array([4, 0]))
    assert why[4 - 4][0][0] == "Unusual amount" and any("Risk score 90%" in t for t, _ in why[0])
    assert ("Night-time payment", 1.0) in why[1] and any(t == "Many payments on this card" for t, _ in why[1])
