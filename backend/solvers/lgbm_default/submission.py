"""LightGBM with default parameters on the shared features."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.base import SolverBase


class Solver(SolverBase):
    name = "lgbm_default"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self.model = lgb.LGBMClassifier(n_estimators=200, random_state=42, verbose=-1, n_jobs=2)
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
