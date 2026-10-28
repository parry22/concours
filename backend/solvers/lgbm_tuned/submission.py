"""LightGBM with class weights, entity history features (customer and terminal aggregates) and tuned trees."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.base import SolverBase


class Solver(SolverBase):
    name = "lgbm_tuned"
    history = True

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        pos = max(1, int(y.sum()))
        neg = max(1, len(y) - pos)
        self.model = lgb.LGBMClassifier(
            n_estimators=600,
            learning_rate=0.03,
            num_leaves=63,
            min_child_samples=40,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            scale_pos_weight=min(50.0, neg / pos),
            random_state=42,
            verbose=-1,
            n_jobs=2,
        )
        self.model.fit(X, y)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]
