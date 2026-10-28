"""Seed the demo through the real API: three named projects at three points in their life.

  "Card fraud review queue, Q4"   stage Improve, v2 active (one improvement round run), improving
  "Churn call list, postpaid"     stage Your model, v1 active, healthy (one list built, one health check)
  "Inbound leads, November"       stage Launch, contest run, packaged, ready to launch

Arena results replay from .cache/arena/ so a reseed takes well under two minutes. Usage: seed.py [api]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]

PROJECTS = [
    {"template": "fraud", "name": "Card fraud review queue, Q4", "contest": ["lgbm_tuned"], "lists": 0, "health": False, "package": False},
    {"template": "churn", "name": "Churn call list, postpaid", "contest": [], "lists": 1, "health": True, "package": False},
    {"template": "leads", "name": "Inbound leads, November", "contest": ["lgbm_tuned", "lgbm_regularized", "lgbm_ensemble"], "lists": 1, "health": False, "package": True},
]


def script(template: str) -> list[str]:
    return json.loads((ROOT / "data" / "templates" / template / "defaults.json").read_text())["replies"]


def call(method, path, body=None, *, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = r.read()
        return out if raw else json.loads(out or b"{}")


def wait_arena(pid: str) -> None:
    while call("GET", f"/projects/{pid}/arena/status")["running"]:
        time.sleep(2)


def seed(cfg: dict) -> str:
    t0 = time.time()
    template, name = cfg["template"], cfg["name"]
    _last = [t0]

    def lap(label: str) -> None:
        now = time.time()
        print(f"[seed:{template}] {label} ({now - _last[0]:.1f}s)")
        _last[0] = now

    p = call("POST", "/projects", {"template": template, "name": name})
    pid = p["id"]
    print(f"[seed:{template}] {name!r} {pid}, {p['profile']['n_rows']} rows")
    lap("created")
    for msg in script(template):
        r = call("POST", f"/projects/{pid}/intake", {"message": msg, "prefer_cache": True})
        print(f"[seed:{template}] intake ({r['source']}): {r['message'][:80]}")
    spec = r["spec"]
    econ = spec.get("economics") or {}
    econ["positive_rate"] = p["profile"]["positive_rate"]
    spec["economics"] = econ
    lap("intake")
    call("PUT", f"/projects/{pid}/spec", spec)
    rep = call("POST", f"/projects/{pid}/protect")
    lap("protect")
    print(f"[seed:{template}] protect: {len(rep['findings'])} findings, {[(x['name'], x['rows']) for x in rep['parts']]}")
    wait_arena(pid)  # the baseline run that builds v1
    lap("v1 run")
    proj = call("GET", f"/projects/{pid}")
    print(f"[seed:{template}] v1: {proj['current_result']}")
    if cfg["contest"]:
        call("POST", f"/projects/{pid}/arena/run", {"solvers": cfg["contest"]})
        wait_arena(pid)
        if os.environ.get("CONCOURS_SEED_AGENT", os.environ.get("BRIEF_SEED_AGENT")) == "1":
            call("POST", f"/projects/{pid}/arena/agent", {})
            while call("GET", f"/projects/{pid}/arena/agent/status")["running"]:
                time.sleep(5)
        lap("improvement round")
        proj = call("GET", f"/projects/{pid}")
        print(f"[seed:{template}] after the round: v{proj['active_model']['version']}, {proj['current_result']} ({proj['improvement_line']})")
    for _ in range(cfg["lists"]):
        lst = call("POST", f"/projects/{pid}/lists?sample=true")
        print(f"[seed:{template}] list: {lst['name']} top {lst['top_n']} of {lst['rows_scored']} (v{lst['model_version']})")
        lap("list")
    if cfg["health"]:
        h = call("POST", f"/projects/{pid}/health?sample=true")
        print(f"[seed:{template}] health: {h['health']} ({h['line']})")
        lap("health")
    if cfg["package"]:
        pk = call("POST", f"/projects/{pid}/package")
        call("GET", f"/projects/{pid}/handoff", raw=True)
        print(f"[seed:{template}] package validation: {pk['validation']}")
        lap("package")
    print(f"[seed:{template}] done in {time.time() - t0:.0f}s")
    return pid


if __name__ == "__main__":
    for cfg in PROJECTS:
        seed(cfg)
