"""End-to-end smoke test against a running backend: create -> spec -> protect -> arena -> finalize.
Usage: python scripts/smoke.py fraud [http://127.0.0.1:8000]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

template = sys.argv[1] if len(sys.argv) > 1 else "fraud"
base = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read() or b"{}")


t0 = time.time()
p = call("POST", "/projects", {"template": template})
pid = p["id"]
print(f"project {pid} stage={p['stage']} rows={p['profile']['n_rows']} spec_target={p['spec']['target_column']}")
spec = p["spec"]
spec["economics"] = {"monthly_volume": 300000, "cost_fn": 120, "cost_fp": 4, "positive_rate": p["profile"]["positive_rate"]}
p = call("PUT", f"/projects/{pid}/spec", spec)
rep = call("POST", f"/projects/{pid}/protect")
print(f"protect: strategy={rep['strategy']} parts={[(x['name'], x['rows'], x['positives']) for x in rep['parts']]} removed={rep['rows_removed']}")
for f in rep["findings"]:
    print(f"  [{f['severity']}] {f['column']}: {f['action']} - {f['reason'][:90]}")
r = call("POST", f"/projects/{pid}/arena/run", {})
print("arena queued", r)
while call("GET", f"/projects/{pid}/arena/status")["running"]:
    time.sleep(5)
    b = call("GET", f"/projects/{pid}/arena/leaderboard")
    print("  ", [(s["solver"], s["status"], s["public_score"]) for s in b["submissions"]])
b = call("POST", f"/projects/{pid}/arena/finalize")
for s in b["submissions"]:
    print(f"  #{s['rank']} {s['solver']:16s} public={s['public_score']} private={s['private_score']} leader={s['is_leader']} {s['error'] or ''}")
print("CARD:", b["business_card"])
print("RAW :", b["raw_metric_line"])
print("SAVE:", b["savings_line"])
print(f"done in {time.time() - t0:.0f}s, project {pid}")
