"""LightGBM with a slow learning rate, strong regularisation and feature subsampling. No entity history."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.base import SolverBase


class Solver(SolverBase):
    name = "lgbm_regularized"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self.model = lgb.LGBMClassifier(
            n_estimators=800,
            learning_rate=0.02,
            num_leaves=31,
            min_child_samples=60,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.7,
            reg_lambda=2.0,
            random_state=42,
            verbose=-1,
            n_jobs=2,
        )
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
