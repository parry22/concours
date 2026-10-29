"""Seed the demo through the real API: two fraud projects.

  "Card fraud review queue, Q4"   v2 active, healthy, improving. Four later weeks with a new fraud pattern wait
                                  behind "Jump forward" for the live drift moment (v3).
  "Marketplace payments"          v1 active, drift injected and detected (slipping), improvement round ready to
                                  run live.

Both use the sample with the injected card-testing pattern (scripts/inject_drift.py) and fixed ID salts, so the
protected data is identical every reseed and arena runs and fitted models replay from .cache/. Usage: seed.py [api]

A third project, "Card fraud on Bittensor" (v1, slipping), is seeded only with `--only=bittensor`: the subnet demo,
where a miner's submission fixes it (subnet/README.md). `CONCOURS_API_KEY` signs in with that key instead of the
demo owner's password.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8000")
ANSWERS = ["200 cases a day", "About 10 per review, no extra fee", "Usually about 30 days"]

PROJECTS = [
    {"name": "Card fraud review queue, Q4", "salt": "concours-demo-q4", "contest": ["lgbm_tuned"], "label_cases": 3, "jump": False},
    {"name": "Marketplace payments", "salt": "concours-demo-marketplace", "contest": [], "label_cases": 0, "jump": True},
    # the Bittensor demo: moved into the new fraud pattern and left slipping, for a miner's submission to fix
    # (see subnet/README.md); only seeded with --only=bittensor
    {"name": "Card fraud on Bittensor", "salt": "concours-demo-bittensor", "contest": [], "label_cases": 0, "jump": True, "optional": True},
]


TOKEN: str | None = None  # an API key for the demo owner, set by sign_in() and revoked when the seed ends
KEY_ID: str | None = None


def _env_file() -> dict[str, str]:
    """CONCOURS_DEMO_* from the environment, else from .env / .env.example at the repo root."""
    out: dict[str, str] = {}
    for name in (".env.example", ".env"):
        f = ROOT / name
        if f.exists():
            for line in f.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    out.update({k: v for k, v in os.environ.items() if k.startswith("CONCOURS_")})
    return out


def sign_in() -> None:
    """Sign up the demo owner on a fresh server (or sign in), then use an API key for everything else.
    Skipped when the server has sign-in off."""
    global TOKEN, KEY_ID
    if os.environ.get("CONCOURS_API_KEY"):
        TOKEN = os.environ["CONCOURS_API_KEY"]  # the caller's key: used as is, not revoked at the end
        print("[seed] using CONCOURS_API_KEY")
        return
    cfg = call("GET", "/auth/config")
    if cfg["auth"] == "off":
        return
    e = _env_file()
    email, password = e.get("CONCOURS_DEMO_EMAIL", "demo@concours.local"), e.get("CONCOURS_DEMO_PASSWORD", "")
    if len(password) < 10:
        raise SystemExit("[seed] set CONCOURS_DEMO_PASSWORD (10+ characters) in .env or the environment")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    path = "/auth/signup" if cfg["first_run"] else "/auth/login"
    body = {"email": email, "password": password, "org_name": "Concours demo"} if cfg["first_run"] else {"email": email, "password": password}
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": "application/json"})
    try:
        opener.open(req, timeout=60).read()
        key = json.loads(opener.open(urllib.request.Request(API + "/auth/keys", data=json.dumps({"name": "demo seed"}).encode(), method="POST",
                                                            headers={"Content-Type": "application/json"}), timeout=60).read())
    except urllib.error.HTTPError as err:
        raise SystemExit(f"[seed] sign-in as {email} failed: {err.code} {err.read()[:300]!r}") from err
    TOKEN, KEY_ID = key["token"], key["id"]
    print(f"[seed] signed in as {email} ({'new owner account' if cfg['first_run'] else 'existing account'})")


def call(method, path, body=None, *, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})}
    req = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            out = r.read()
            return out if raw else json.loads(out or b"null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[seed] {method} {path} failed: {e.code} {e.read()[:400]!r}") from e


def wait_arena(pid: str) -> None:
    while call("GET", f"/projects/{pid}/arena/status")["running"]:
        time.sleep(1)


def seed(cfg: dict) -> str:
    t0 = time.time()
    last = [t0]
    tag = cfg["name"].split(",")[0].split()[0].lower()

    def lap(label: str) -> None:
        now = time.time()
        print(f"[seed:{tag}] {label} ({now - last[0]:.1f}s)")
        last[0] = now

    p = call("POST", "/projects", {"template": "fraud", "name": cfg["name"], "sample": True, "sample_file": "transactions_drift.csv", "salt": cfg["salt"]})
    pid = p["id"]
    lap(f"created {pid}, {p['profile']['n_rows']:,} payments")
    sch = call("GET", f"/projects/{pid}/schema")
    call("PUT", f"/projects/{pid}/schema", {"mapping": {f["name"]: f["column"] for f in sch["fields"]}})
    lap("columns mapped")
    for a in ANSWERS:
        call("POST", f"/projects/{pid}/intake", {"message": a})
    rep = call("POST", f"/projects/{pid}/protect")
    lap(f"protected: {[(x['name'], x['rows']) for x in rep['parts']]}, as of {rep['maturity']['as_of']}")
    wait_arena(pid)
    proj = call("GET", f"/projects/{pid}")
    lap(f"v1: {proj['current_result']}")
    if cfg["contest"]:
        call("POST", f"/projects/{pid}/arena/run", {"solvers": cfg["contest"]})
        wait_arena(pid)
        proj = call("GET", f"/projects/{pid}")
        lap(f"round: v{proj['active_model']['version']} {proj['current_result']} ({proj['improvement_line']})")
    if cfg["jump"]:
        d = call("POST", f"/projects/{pid}/clock", {"days": 28, "auto_round": False})
        lap(f"jumped to {d['as_of']}: {d['line']}")
    else:
        d = call("POST", f"/projects/{pid}/drift")
        q = call("GET", f"/projects/{pid}/queue")
        for c in q["cases"][: cfg["label_cases"]]:
            call("POST", f"/projects/{pid}/queue/{c['transaction_id']}/label", {"label": "fraud" if c["rank"] != 2 else "not_fraud"})
        lap(f"health: {d['line']} queue: {len(q['cases'])} cases for {q['day']}")
    print(f"[seed:{tag}] done in {time.time() - t0:.0f}s")
    return pid


if __name__ == "__main__":
    t = time.time()
    sign_in()
    try:
        only = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), None)
        if "--auth-only" not in sys.argv:
            for cfg in PROJECTS:
                tag = cfg["name"].split(",")[0].split()[-1].lower()
                if (only and only not in (tag, cfg["name"])) or (not only and cfg.get("optional")):
                    continue
                seed(cfg)
            print(f"[seed] all done in {time.time() - t:.0f}s")
    finally:
        if KEY_ID:
            call("DELETE", f"/auth/keys/{KEY_ID}")  # the seed's key is not left behind
