"""Seed both templates through the real API so the demo leaderboard replays instantly. Usage: seed.py [api]"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SCRIPTS = {
    "fraud": [
        "We want to catch more card fraud without annoying good customers.",
        "About 1 in 1000 false alarms is fine.",
        "A missed fraud costs us about 120 dollars, a blocked good customer about 4 dollars. We see 300000 transactions a month.",
    ],
    "churn": [
        "We want to know which customers are about to leave so we can call them first.",
        "We can call about 10 percent of customers each month.",
        "A lost customer is worth about 60 dollars a month, a wasted call costs 3 dollars. We have 3000 customers.",
    ],
}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read() or b"{}")


def seed(template: str) -> str:
    t0 = time.time()
    p = call("POST", "/projects", {"template": template})
    pid = p["id"]
    print(f"[seed:{template}] project {pid}, {p['profile']['n_rows']} rows")
    for msg in SCRIPTS[template]:
        r = call("POST", f"/projects/{pid}/intake", {"message": msg})
        print(f"[seed:{template}] intake ({r['source']}): {r['message'][:80]}")
    spec = r["spec"]
    econ = spec.get("economics") or {}
    econ["positive_rate"] = p["profile"]["positive_rate"]
    spec["economics"] = econ
    call("PUT", f"/projects/{pid}/spec", spec)
    rep = call("POST", f"/projects/{pid}/protect")
    print(f"[seed:{template}] protect: {len(rep['findings'])} findings, {[(x['name'], x['rows']) for x in rep['parts']]}")
    call("POST", f"/projects/{pid}/arena/run", {})
    while call("GET", f"/projects/{pid}/arena/status")["running"]:
        time.sleep(3)
    b = call("POST", f"/projects/{pid}/arena/finalize")
    print(f"[seed:{template}] {b['business_card']}")
    pk = call("POST", f"/projects/{pid}/package")
    print(f"[seed:{template}] package validation: {pk['validation']} ({time.time() - t0:.0f}s)")
    return pid


if __name__ == "__main__":
    for t in ("fraud", "churn"):
        seed(t)
