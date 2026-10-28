"""Baseline: logistic regression with standard scaling."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common.base import SolverBase


class Solver(SolverBase):
    name = "baseline_logreg"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self.model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced"))
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
