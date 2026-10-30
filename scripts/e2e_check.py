"""Exercise the demo flow against a running Concours on a throwaway project, then delete it.

Creates a project from the sample file with the same salt as the seeded Q4 project (so the arena cache applies),
maps columns, answers the three questions, protects, waits for v1, runs the tuned contest, jumps the clock four
weeks with an automatic round, and reports timings and the resulting model version. Nothing seeded is touched.

Usage: python scripts/e2e_check.py [http://127.0.0.1:8000]
Signs in with CONCOURS_DEMO_EMAIL / CONCOURS_DEMO_PASSWORD from the environment or the repo-root .env.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ["200 cases a day", "About 10 per review, no extra fee", "Usually about 30 days"]

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=1800) as r:
        out = r.read()
        return json.loads(out or b"null")


def creds() -> tuple[str, str]:
    e = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                e.setdefault(k.strip(), v.strip())
    return e.get("CONCOURS_DEMO_EMAIL", "demo@concours.local"), e.get("CONCOURS_DEMO_PASSWORD", "")


def wait_arena(pid: str) -> float:
    t0 = time.time()
    while call("GET", f"/projects/{pid}/arena/status")["running"]:
        time.sleep(1)
    return time.time() - t0


def main() -> int:
    email, password = creds()
    call("POST", "/auth/login", {"email": email, "password": password})
    print(f"[e2e] signed in as {email}")
    t0 = time.time()
    p = call("POST", "/projects", {"template": "fraud", "name": "E2E check (delete me)", "sample": True,
                                   "sample_file": "transactions_drift.csv", "salt": "concours-demo-q4", "protect_version": 1})
    pid = p["id"]
    print(f"[e2e] created {pid}: {p['profile']['n_rows']:,} payments ({time.time() - t0:.0f}s)")
    try:
        sch = call("GET", f"/projects/{pid}/schema")
        call("PUT", f"/projects/{pid}/schema", {"mapping": {f["name"]: f["column"] for f in sch["fields"]}})
        for a in ANSWERS:
            call("POST", f"/projects/{pid}/intake", {"message": a})
        t = time.time()
        rep = call("POST", f"/projects/{pid}/protect")
        print(f"[e2e] protected in {time.time() - t:.0f}s: {[(x['name'], x['rows']) for x in rep['parts']]}")
        t = time.time()
        wait_arena(pid)
        proj = call("GET", f"/projects/{pid}")
        print(f"[e2e] v1 in {time.time() - t:.0f}s: {proj['current_result']}")
        t = time.time()
        call("POST", f"/projects/{pid}/arena/run", {"solvers": ["lgbm_tuned"]})
        wait_arena(pid)
        proj = call("GET", f"/projects/{pid}")
        print(f"[e2e] contest in {time.time() - t:.0f}s: v{proj['active_model']['version']} {proj['current_result']}")
        t = time.time()
        d = call("POST", f"/projects/{pid}/clock", {"days": 28, "auto_round": True})
        print(f"[e2e] jumped to {d.get('as_of')}: {d.get('line', '')}")
        wait_arena(pid)
        proj = call("GET", f"/projects/{pid}")
        board = call("GET", f"/projects/{pid}/arena/leaderboard")
        secs = {s["solver"]: s.get("eval_seconds") for s in board["submissions"]}
        print(f"[e2e] drift round in {time.time() - t:.0f}s: v{proj['active_model']['version']} {proj['current_result']}")
        print(f"[e2e] attempts (eval seconds as recorded): {secs}")
        print(f"[e2e] total {time.time() - t0:.0f}s")
    finally:
        call("DELETE", f"/projects/{pid}")
        print(f"[e2e] deleted {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
