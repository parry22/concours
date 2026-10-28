"""Brief gym_v1 REFEREE. Holds the hidden leaderboard and holdout data, drives the player, scores with shared metrics.

Writes /data/result.json as GameResult:
  raw_scores[0]  = private (holdout) primary metric, the number Apex reads
  metadata       = {public_score, private_score, primary_metric, metric_params, secondary: {...},
                    breakdown: {...}, eval_time_in_seconds, rows: {...}}
Player failures (PlayerError or malformed responses) score 0 with terminal_reason "player_error".
"""
from __future__ import annotations

import csv
import json
import math
import os
import time
from pathlib import Path

import metrics  # shared/metrics.py copied into the image
from gym_v1.client import PlayerClient, PlayerError
from gym_v1.referee import GameResult, Referee, RefereeContext

DATA_DIR = Path(os.environ.get("REFEREE_DATA_DIR", "/app/data"))
CHUNK = 5000
DEADLINE_MS = 60_000


def _read_csv(path: Path) -> tuple[list[str], list[list]]:
    with path.open(newline="") as f:
        r = csv.reader(f)
        cols = next(r)
        rows = [[_num(v) for v in row] for row in r]
    return cols, rows


def _num(v: str):
    if v == "":
        return None
    try:
        if v.lstrip("-").isdigit():
            return int(v)
        return float(v)
    except ValueError:
        return v


def _labels(path: Path) -> list[int]:
    with path.open(newline="") as f:
        r = csv.reader(f)
        next(r)
        return [int(row[0]) for row in r]


class BriefReferee(Referee):
    readiness_timeout_s = 600.0  # training-heavy players may take a while to load; Apex norm is 60 s

    def score_split(self, player: PlayerClient, name: str) -> tuple[list[float], list[int], dict]:
        cols, rows = _read_csv(DATA_DIR / f"{name}.csv")
        y = _labels(DATA_DIR / f"{name}_labels.csv")
        scores: list[float] = []
        faults = 0
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            try:
                action = player.act(observation={"columns": cols, "rows": chunk}, deadline_ms=DEADLINE_MS)
                got = action.get("scores") if isinstance(action, dict) else None
                if not isinstance(got, list) or len(got) != len(chunk):
                    raise PlayerError(f"bad action shape for chunk {i}")
                vals = []
                for v in got:
                    fv = float(v)
                    vals.append(fv if math.isfinite(fv) else 0.0)
                scores.extend(vals)
            except (PlayerError, TypeError, ValueError) as e:
                faults += 1
                scores.extend([0.0] * len(chunk))
                self.trace({"split": name, "chunk": i, "fault": str(e)[:200]})
        return scores, y, {"rows": len(rows), "faulted_chunks": faults}

    def play_game(self, ctx: RefereeContext, players: list[PlayerClient]) -> GameResult:
        start = time.monotonic()
        cfg = ctx.config or {}
        primary = cfg.get("primary_metric", "recall_at_fpr")
        params = cfg.get("metric_params", {})
        secondary = cfg.get("secondary_metric")
        player = players[0]
        try:
            player.reset(match_id=ctx.match_id, player_index=0, seed=ctx.seed, config=cfg, timeout_s=float(cfg.get("reset_timeout_s", 900)))
        except PlayerError as e:
            return GameResult(raw_scores=[0.0], winner=-1, terminal_reason="player_error", steps=0,
                              metadata={"error": str(e)[:500], "eval_time_in_seconds": time.monotonic() - start})
        out: dict = {"primary_metric": primary, "metric_params": params, "secondary_metric": secondary, "splits": {}}
        results = {}
        total_faults = 0
        for split in ("leaderboard", "holdout"):
            s, y, info = self.score_split(player, split)
            total_faults += info["faulted_chunks"]
            results[split] = {
                "primary": metrics.compute(primary, y, s, params),
                "secondary": metrics.compute(secondary, y, s) if secondary else None,
                "positives": int(sum(y)),
                **info,
            }
        out["splits"] = results
        out["public_score"] = results["leaderboard"]["primary"]
        out["private_score"] = results["holdout"]["primary"]
        out["secondary"] = {"public": results["leaderboard"]["secondary"], "private": results["holdout"]["secondary"]}
        out["eval_time_in_seconds"] = time.monotonic() - start
        reason = "scored" if total_faults == 0 else "scored_with_player_faults"
        return GameResult(raw_scores=[out["private_score"]], winner=0, terminal_reason=reason,
                          steps=sum(r["rows"] for r in results.values()), metadata=out)


if __name__ == "__main__":
    BriefReferee().run()
