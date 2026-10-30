"""The real-customer path, cold, plus an outside solver: upload a CSV (not the sample), map, settings, protect, v1 in
Docker (nothing cached for a new file), then a solver key, a submission through /solve, its measurement and gates.

Usage: python scripts/e2e_outside.py [http://127.0.0.1:8000] [--file path.csv] [--keep]
Signs in with CONCOURS_DEMO_EMAIL / CONCOURS_DEMO_PASSWORD from the environment or the repo-root .env.
Default file: workspace/audit/messy.csv (the journey audit's messy export: mixed dates, currency symbols, blanks,
two leak columns, a card-number column). The submission is backend/solvers/lgbm_velocity/submission.py sent as an
outside solver's code, so it is scored from scratch in the container. --keep leaves the project for a look.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
API = args[0] if args else "http://127.0.0.1:8000"
KEEP = "--keep" in sys.argv
FILE = Path(sys.argv[sys.argv.index("--file") + 1]) if "--file" in sys.argv else ROOT / "workspace" / "audit" / "messy.csv"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method: str, path: str, body: dict | None = None, headers: dict | None = None, retries: int = 0) -> dict:
    """`retries` > 0 for polling reads: a 5xx (the hosted copy once answered "database is locked") is retried."""
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    for attempt in range(retries + 1):
        req = urllib.request.Request(API + path, data=data, method=method, headers=h)
        try:
            with opener.open(req, timeout=3600) as r:
                out = r.read()
                return json.loads(out or b"null")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code >= 500 and attempt < retries:
                print(f"[e2e] {method} {path}: {e.code}, retrying ({detail[:80]})")
                time.sleep(3)
                continue
            raise SystemExit(f"{method} {path}: {e.code} {detail}") from e
    raise SystemExit("unreachable")


def upload(path: str, file: Path) -> dict:
    boundary = uuid.uuid4().hex
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file.name}\"\r\n"
            "Content-Type: text/csv\r\n\r\n").encode()
    body = head + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(API + path, data=body, method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with opener.open(req, timeout=600) as r:
        return json.loads(r.read())


def creds() -> tuple[str, str]:
    e = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                e.setdefault(k.strip(), v.strip().strip('"'))
    return e["CONCOURS_DEMO_EMAIL"], e["CONCOURS_DEMO_PASSWORD"]


def wait_arena(pid: str) -> float:
    t0 = time.time()
    while call("GET", f"/projects/{pid}/arena/status", retries=5)["running"]:
        time.sleep(2)
    return time.time() - t0


def main() -> int:
    if call("GET", "/auth/config").get("auth") == "off":
        email = "local"
    else:
        email, password = creds()
        call("POST", "/auth/login", {"email": email, "password": password})
    print(f"[e2e] signed in as {email}; file {FILE} ({FILE.stat().st_size / 1e6:.1f} MB)")
    t0 = time.time()
    p = call("POST", "/projects", {"template": "fraud", "name": "Outside solver check (delete me)", "sample": False})
    pid = p["id"]
    try:
        prof = upload(f"/projects/{pid}/data", FILE)
        print(f"[e2e] uploaded: {prof['n_rows']:,} rows, {len(prof['columns'])} columns ({time.time() - t0:.0f}s)")
        sch = call("GET", f"/projects/{pid}/schema")
        mapping = {f["name"]: f["column"] for f in sch["fields"]}
        missing = [f["name"] for f in sch["fields"] if f.get("required") and not f["column"]]
        if missing:
            raise SystemExit(f"[e2e] required fields not suggested: {missing}; mapping so far {mapping}")
        t = time.time()
        call("PUT", f"/projects/{pid}/schema", {"mapping": mapping})
        print(f"[e2e] columns confirmed in {time.time() - t:.0f}s: {mapping}")
        call("PUT", f"/projects/{pid}/fraud-settings", {"daily_capacity": 200, "review_cost": 10, "fraud_fee": 0, "label_delay_days": 30})
        t = time.time()
        rep = call("POST", f"/projects/{pid}/protect")
        print(f"[e2e] protected in {time.time() - t:.0f}s: {[(x['name'], x['rows']) for x in rep['parts']]}")
        print(f"[e2e] findings: {[(f['check'], f['column']) for f in rep['findings'] if f['severity'] == 'high']}")
        t = time.time()
        wait_arena(pid)
        proj = call("GET", f"/projects/{pid}")
        print(f"[e2e] v1 in {time.time() - t:.0f}s (cold Docker): {proj['current_result']}")

        key = call("POST", f"/projects/{pid}/solvers/keys", {"name": "Ada (outside)"})
        h = {"X-Solver-Key": key["token"]}
        me = call("GET", "/solve/me", headers=h)
        print(f"[e2e] solver key for {me['solver']}: v{me['active_version']} ${me['active_per_day']:,.0f}/day, bar ${me['bar_per_day']:,.0f}/day")
        req = urllib.request.Request(API + "/solve/kit", headers=h)
        with opener.open(req, timeout=60) as r:
            kit = r.read()
        print(f"[e2e] kit: {len(kit):,} bytes zip")
        code = (ROOT / "backend" / "solvers" / "lgbm_velocity" / "submission.py").read_text()
        t = time.time()
        a = call("POST", "/solve/submissions", {"code": code}, headers=h)
        print(f"[e2e] submitted {a['id']}: {a['status']}")
        while a["status"] in ("queued", "running"):
            time.sleep(3)
            a = call("GET", f"/solve/submissions/{a['id']}", headers=h, retries=5)
        time.sleep(3)  # the gates are stored a moment after the score
        a = call("GET", f"/solve/submissions/{a['id']}", headers=h, retries=5)
        gates = [(g.get("name"), g.get("passed")) for g in a["gates"]]
        print(f"[e2e] outside attempt measured in {time.time() - t:.0f}s: {a['business_value'] or a['error']}; gates {gates}; "
              f"active={a['active']} version={a['version']}")
        proj = call("GET", f"/projects/{pid}")
        print(f"[e2e] project now: v{proj['active_model']['version']} {proj['current_result']}")
        keys = call("GET", f"/projects/{pid}/solvers/keys")
        print(f"[e2e] keys: {[(k['name'], k['attempts']) for k in keys]}")
        print(f"[e2e] total {time.time() - t0:.0f}s")
    finally:
        if KEEP:
            print(f"[e2e] kept project {pid}")
        else:
            call("DELETE", f"/projects/{pid}")
            print(f"[e2e] deleted {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
