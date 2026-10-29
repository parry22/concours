"""Score rows through the player sandbox, with no referee data involved.

Runs inside the referee image (same gym_v1 client, same limits), mounted at /app/score_rows.py and started with
`python /app/score_rows.py` instead of referee.py. Reads /rows/rows.csv (features only, the columns the player was
trained on), drives /reset and /act exactly as the referee does, and writes /data/scores.csv. Concours uses it to
score today's queue and the drift check with a version whose code came from outside (an agent attempt or a chain
miner), so that code never runs on the host.
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")
from gym_v1.client import PlayerClient  # noqa: E402

ROWS = Path(os.environ.get("SCORE_ROWS_PATH", "/rows/rows.csv"))
OUT = Path(os.environ.get("SCORE_OUT_PATH", "/data/scores.csv"))
CHUNK = 5000
DEADLINE_MS = 60_000


def _num(v: str):
    if v == "":
        return None
    try:
        if v.lstrip("-").isdigit():
            return int(v)
        return float(v)
    except ValueError:
        return v


def main() -> int:
    cfg = json.loads(os.environ.get("CONFIG_JSON") or "{}")
    url = os.environ["PLAYER_URLS"].split(",")[0]
    timeout = float(cfg.get("reset_timeout_s", 900))
    player = PlayerClient(url)
    player.wait_until_ready(timeout)
    player.reset(match_id=os.environ.get("MATCH_ID", "score"), player_index=0, seed=int(os.environ.get("SEED", "0")), config=cfg, timeout_s=timeout)
    with ROWS.open(newline="") as f:
        r = csv.reader(f)
        cols = next(r)
        rows = [[_num(v) for v in row] for row in r]
    scores: list[float] = []
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i : i + CHUNK]
        action = player.act(observation={"columns": cols, "rows": chunk}, deadline_ms=DEADLINE_MS)
        got = action.get("scores") if isinstance(action, dict) else None
        if not isinstance(got, list) or len(got) != len(chunk):
            raise SystemExit(f"bad action shape for chunk {i}")
        for v in got:
            fv = float(v)
            scores.append(fv if math.isfinite(fv) else 0.0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["score"])
        w.writerows([[f"{v:.6g}"] for v in scores])
    print(f"scored {len(scores)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
