"""Concours gym_v1 REFEREE. Holds the hidden leaderboard and holdout data, drives the player, scores with shared metrics.

Writes /data/result.json as GameResult:
  raw_scores[0]  = private (holdout) primary metric, the number Apex reads
  metadata       = {primary_metric, metric_params, public_score, secondary_public, rows, eval_time_in_seconds, seconds_per_10k}
Also writes /data/details.json (per-split numbers, the private score, the queue summary per split, the lift
breakdown) and /data/scores_<split>.csv (one score per row, split order), so Concours can price the operating point
and run its gates without re-fitting. Those files stay with the arena logs and never enter the handoff; the private
number is never in result.json metadata, which the platform may show on its dashboard.
Fraud metrics: `fraud_amount_per_day` (money inside capacity) and, from competition v0.2.0, `fraud_lift_in_capacity`
(share of the catchable money beyond the largest-payments rule). Both need `<split>_meta.csv` (day, amount).
Player failures (PlayerError or malformed responses) score 0 with terminal_reason "player_error".
Fraud: when `<split>_meta.csv` (day, amount) sits next to the labels, the capacity metric reads it, and the
metadata carries the queue summary per split and `seconds_per_10k` (holdout scoring time per 10,000 rows).
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
OUT_DIR = Path(os.environ.get("REFEREE_OUT_DIR", "/data"))  # the same volume result.json lands in
CHUNK = 5000
DEADLINE_MS = 60_000
FRAUD_METRICS = ("fraud_amount_per_day", "fraud_lift_in_capacity")


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


def _meta(name: str) -> dict | None:
    path = DATA_DIR / f"{name}_meta.csv"
    if not path.exists():
        return None
    with path.open(newline="") as f:
        r = csv.DictReader(f)
        rows = list(r)
    return {"day": [x["day"] for x in rows], "amount": [float(x["amount"] or 0) for x in rows]}


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
        t0 = time.monotonic()
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
                self.trace({"split": name, "chunk": i, "fault": type(e).__name__})  # never a value from a row
        secs = time.monotonic() - t0
        return scores, y, {"rows": len(rows), "faulted_chunks": faults, "seconds_per_10k": round(secs / max(1, len(rows)) * 10_000, 3)}

    def _dump_scores(self, split: str, scores: list[float]) -> None:
        try:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            with (OUT_DIR / f"scores_{split}.csv").open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["score"])
                w.writerows([[f"{v:.6g}"] for v in scores])
        except OSError as e:  # scoring must not fail because the side file could not be written
            self.trace({"split": split, "scores_file_error": str(e)[:200]})

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
                              metadata={"error": f"{type(e).__name__}: {str(e)[:160]}", "eval_time_in_seconds": time.monotonic() - start})
        out: dict = {"primary_metric": primary, "metric_params": params, "secondary_metric": secondary, "splits": {}}
        results = {}
        total_faults = 0
        for split in ("leaderboard", "holdout"):
            s, y, info = self.score_split(player, split)
            total_faults += info["faulted_chunks"]
            self._dump_scores(split, s)
            meta = _meta(split)
            results[split] = {
                "primary": metrics.compute(primary, y, s, params, meta),
                "secondary": metrics.compute(secondary, y, s) if secondary else None,
                "positives": int(sum(y)),
                **info,
            }
            if meta is not None and primary in FRAUD_METRICS:
                cap, fee, cost = int(params.get("capacity", 200)), float(params.get("fee", 0.0)), float(params.get("review_cost", 0.0))
                q = metrics.fraud_queue(y, s, meta["amount"], meta["day"], cap, fee, cost)
                results[split]["fraud"] = metrics.fraud_summary(q)
                results[split]["lift"] = metrics.fraud_lift_in_capacity(y, s, meta["amount"], meta["day"], cap, fee, cost)
        out["splits"] = results
        out["public_score"] = results["leaderboard"]["primary"]
        out["private_score"] = results["holdout"]["primary"]
        out["secondary"] = {"public": results["leaderboard"]["secondary"], "private": results["holdout"]["secondary"]}
        out["eval_time_in_seconds"] = time.monotonic() - start
        out["seconds_per_10k"] = results["holdout"].get("seconds_per_10k")
        reason = "scored" if total_faults == 0 else "scored_with_player_faults"
        self._dump_details(out)
        # result.json is what the platform reads and may show on its dashboard: the private number travels only in
        # raw_scores (hidden during a round); per-split detail stays in the side file for the competition owner.
        lean = {"primary_metric": primary, "metric_params": params, "secondary_metric": secondary,
                "public_score": out["public_score"], "secondary_public": results["leaderboard"]["secondary"],
                "rows": {k: v["rows"] for k, v in results.items()}, "faulted_chunks": total_faults,
                "eval_time_in_seconds": out["eval_time_in_seconds"], "seconds_per_10k": out["seconds_per_10k"]}
        return GameResult(raw_scores=[out["private_score"]], winner=0, terminal_reason=reason,
                          steps=sum(r["rows"] for r in results.values()), metadata=lean)

    def _dump_details(self, out: dict) -> None:
        try:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUT_DIR / "details.json").write_text(json.dumps(out, default=float))
        except OSError as e:
            self.trace({"details_file_error": str(e)[:200]})


if __name__ == "__main__":
    BriefReferee().run()
