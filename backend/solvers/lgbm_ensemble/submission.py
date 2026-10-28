"""Five regularised LightGBM models with different seeds, probabilities averaged."""
from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from common.base import SolverBase

SEEDS = (1, 2, 3, 4, 5)


class Solver(SolverBase):
    name = "lgbm_ensemble"

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> None:
        self.models = []
        for seed in SEEDS:
            m = lgb.LGBMClassifier(
                n_estimators=800,
                learning_rate=0.02,
                num_leaves=31,
                min_child_samples=60,
                subsample=0.8,
                subsample_freq=1,
                colsample_bytree=0.7,
                reg_lambda=2.0,
                random_state=seed,
                verbose=-1,
                n_jobs=2,
            )
            m.fit(X, y)
            self.models.append(m)
        self.model = self.models[0]

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return np.mean([m.predict_proba(X)[:, 1] for m in self.models], axis=0)
