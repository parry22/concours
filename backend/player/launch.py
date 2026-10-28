"""Brief gym_v1 PLAYER server. Wraps a plain-Python solver (submission.py exposing `Solver`) behind the Apex contract.

Contract (verified against apex-competitions-builder @ 49eb05e):
  - The platform writes the miner submission to /app/submission.py and runs this file.
  - /health reports ready once the submission module has loaded.
  - /reset trains the solver on the public train split baked into this image (/app/data/train.csv).
  - /act receives {"columns": [...], "rows": [[...], ...]} and returns {"scores": [float, ...]}.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, "/app")  # so `from common.base import SolverBase` resolves inside the image
from gym_v1.player import Player, serve  # noqa: E402  (vendored)

SUBMISSION_PATH = Path("/app/submission.py")
DATA_DIR = Path("/app/data")


def _load_submission():
    spec = importlib.util.spec_from_file_location("submission", SUBMISSION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class BriefPlayer(Player):
    def __init__(self) -> None:
        self._submission = _load_submission()  # a broken submission fails readiness
        self._transform = json.loads((DATA_DIR / "transform.json").read_text()) if (DATA_DIR / "transform.json").exists() else {}
        self._solver = None

    def reset(self, match_id: str, player_index: int, seed: int, config: dict[str, Any]) -> None:
        np.random.seed(seed)
        solver = self._submission.Solver(self._transform)
        train = pd.read_csv(DATA_DIR / "train.csv")
        max_rows = int(config.get("max_train_rows", 0) or 0)
        if max_rows and len(train) > max_rows:
            train = train.tail(max_rows)
        solver.fit_frame(train)
        self._solver = solver

    def act(self, observation: Any, deadline_ms: int) -> Any:  # noqa: ARG002
        if self._solver is None:
            raise RuntimeError("reset was not called before act")
        batch = pd.DataFrame(observation["rows"], columns=observation["columns"])
        scores = self._solver.score_frame(batch)
        scores = np.nan_to_num(np.asarray(scores, dtype=float), nan=0.0, posinf=1.0, neginf=0.0)
        return {"scores": [float(x) for x in scores]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(BriefPlayer(), port=args.port, readiness_path="/health")
