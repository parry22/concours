"""concours: the whole fraud workflow from a terminal, against a Concours server (local or production).

Standard library only. Sign in once with `concours login`; the API key is kept in ~/.config/concours/config.json
(mode 600). CONCOURS_URL, CONCOURS_API_KEY and CONCOURS_PROJECT override it, for scripts and CI.

  concours login --url https://fraud.example.com/api --email you@company.com
  concours new --name "Card fraud" --file payments.csv     # or --sample
  concours map                                             # shows the suggested mapping, confirms it
  concours settings --capacity 200 --review-cost 10 --delay 30
  concours protect                                         # protection, then waits for version 1
  concours queue --csv today.csv                           # today's review queue
  concours label 1474722 fraud
  concours improve                                         # an improvement round, with the five gates
  concours jump --days 28                                  # simulated clock (sample data)
  concours package --out handoff.zip
  concours package --repo repo.zip                         # the private competition repo, holdout included

Add --json to most commands for machine output. `concours <command> --help` for options.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

__version__ = "0.3.0"
CONFIG = Path(os.environ.get("CONCOURS_CONFIG", Path.home() / ".config" / "concours" / "config.json"))
DEFAULT_URL = "http://127.0.0.1:8000"
FIELDS = ("transaction_id", "transaction_time", "amount", "customer_id", "is_fraud", "merchant_or_terminal_id", "currency", "label_time")
REQUIRED = FIELDS[:5]


class CliError(Exception):
    pass


# ---------- config ----------


def load_config() -> dict:
    cfg = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    for k, env in (("url", "CONCOURS_URL"), ("api_key", "CONCOURS_API_KEY"), ("project", "CONCOURS_PROJECT")):
        if os.environ.get(env):
            cfg[k] = os.environ[env]
    cfg.setdefault("url", DEFAULT_URL)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in cfg.items() if k in ("url", "api_key", "project", "key_id")}
    tmp = CONFIG.with_suffix(".tmp")
    tmp.write_text(json.dumps(keep, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(CONFIG)


# ---------- HTTP ----------


class Client:
    def __init__(self, url: str, api_key: str | None = None):
        self.url = url.rstrip("/")
        self.key = api_key
        self.cookies: dict[str, str] = {}

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"User-Agent": f"concours-cli/{__version__}", "Accept": "application/json"}
        if self.key:
            h["Authorization"] = f"Bearer {self.key}"
        if self.cookies:
            h["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        return {**h, **(extra or {})}

    def raw(self, method: str, path: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 1800):
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=self._headers(headers))
        try:
            r = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            try:
                detail = json.loads(body).get("detail", body)
            except json.JSONDecodeError:
                detail = body
            if e.code == 401:
                raise CliError(f"{detail} Run `concours login`.") from e
            raise CliError(f"{method} {path}: {e.code} {detail if isinstance(detail, str) else json.dumps(detail)}") from e
        except urllib.error.URLError as e:
            raise CliError(f"Could not reach {self.url}: {e.reason}. Is the server running?") from e
        for c in r.headers.get_all("Set-Cookie") or []:
            name, _, rest = c.partition("=")
            self.cookies[name.strip()] = rest.split(";", 1)[0]
        return r

    def call(self, method: str, path: str, body=None, timeout: float = 1800):
        data = json.dumps(body).encode() if body is not None else None
        r = self.raw(method, path, data, {"Content-Type": "application/json"} if data is not None else None, timeout)
        out = r.read()
        return json.loads(out) if out else None

    def upload(self, path: str, file: Path):
        boundary = uuid.uuid4().hex
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{file.name}\"\r\n"
                "Content-Type: text/csv\r\n\r\n").encode()
        body = head + file.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        r = self.raw("POST", path, body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        return json.loads(r.read())

    def stream(self, path: str):
        """Server-sent events: yields (event, data) until the server closes the stream."""
        r = self.raw("GET", path, headers={"Accept": "text/event-stream"}, timeout=3600)
        event, data = "message", []
        for line in r:
            line = line.decode(errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
            elif line == "":
                if data:
                    try:
                        payload = json.loads("\n".join(data))
                    except json.JSONDecodeError:
                        payload = {}
                    yield event, payload
                event, data = "message", []


# ---------- output ----------


def money(x) -> str:
    if x is None:
        return "n/a"
    return f"{'-' if float(x) < 0 else ''}${abs(float(x)):,.0f}"


def pct(x) -> str:
    return "n/a" if x is None else f"{float(x) * 100:.1f}%"


def table(rows: list[list], header: list[str]) -> str:
    cells = [header] + [[("" if c is None else str(c)) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    lines = ["  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip() for r in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def emit(args, data, human) -> None:
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2, default=str))
    else:
        human()


# ---------- helpers ----------


def client(cfg: dict) -> Client:
    return Client(cfg["url"], cfg.get("api_key"))


def project_id(args, cfg: dict) -> str:
    pid = getattr(args, "project", None) or cfg.get("project")
    if not pid:
        raise CliError("No project chosen. Use --project ID or `concours use ID` (see `concours projects`).")
    return pid


def wait_round(c: Client, pid: str, quiet: bool = False) -> None:
    """Follow the live events until the round finishes, printing log lines."""
    if not c.call("GET", f"/projects/{pid}/arena/status")["running"]:
        return
    try:
        for event, data in c.stream(f"/projects/{pid}/arena/stream"):
            if event == "log" and not quiet:
                print(f"  {data.get('line', '')}")
            elif event == "model_promoted" and not quiet:
                print(f"  promoted v{data.get('version')}: {data.get('business_value')}")
            elif event == "run_complete":
                break
            elif event == "ping" and not c.call("GET", f"/projects/{pid}/arena/status")["running"]:
                break
    except CliError:  # a proxy dropped the stream: fall back to polling
        while c.call("GET", f"/projects/{pid}/arena/status")["running"]:
            time.sleep(3)


def summary(p: dict) -> str:
    m = p.get("active_model")
    lines = [f"{p['name']}  ({p['id']})"]
    if p.get("profile"):
        lines.append(f"  payments      {p['profile']['n_rows']:,}")
    lines.append(f"  stage         {p['stage']}{'  (columns confirmed)' if p.get('schema_confirmed') else ''}")
    if p.get("as_of"):
        lines.append(f"  today         {p['as_of']}")
    if m:
        lines.append(f"  model         v{m['version']}  {p.get('model_status')}")
        lines.append(f"  caught/day    {money(p.get('money_per_day'))}   net/day {money(p.get('net_per_day'))}")
        if m.get("improvement_line"):
            lines.append(f"                {m['improvement_line']}")
    if p.get("drift") and p["drift"].get("line"):
        lines.append(f"  health        {p['drift']['line']}")
    st = p.get("fraud_settings")
    if st:
        lines.append(f"  settings      {st['daily_capacity']} cases/day, ${st['review_cost']:.2f}/review, fee ${st['fraud_fee']:.2f}, "
                     f"{st['label_delay_days']} days to confirm")
    return "\n".join(lines)


# ---------- commands ----------


def cmd_login(args, cfg):
    url = (args.url or cfg.get("url") or DEFAULT_URL).rstrip("/")
    c = Client(url)
    conf = c.call("GET", "/auth/config")
    if conf["auth"] == "off":
        cfg.update(url=url, api_key=None)
        save_config(cfg)
        print(f"{url}: sign-in is off on this server; no key needed.")
        return
    if args.api_key:
        c.key = args.api_key
        me = c.call("GET", "/auth/me")
        cfg.update(url=url, api_key=args.api_key)
        save_config(cfg)
        print(f"Signed in as {me['email']} ({me['org_name']}).")
        return
    email = args.email or input("Email: ").strip()
    password = os.environ.get("CONCOURS_PASSWORD") or getpass.getpass("Password: ")
    c.call("POST", "/auth/login", {"email": email, "password": password})
    key = c.call("POST", "/auth/keys", {"name": f"cli@{socket.gethostname()}"})
    me = c.call("GET", "/auth/me")
    cfg.update(url=url, api_key=key["token"], key_id=key["id"])
    save_config(cfg)
    print(f"Signed in as {me['email']} ({me['org_name']}). API key {key['prefix']}… saved to {CONFIG}.")


def cmd_logout(args, cfg):
    if cfg.get("api_key") and cfg.get("key_id"):
        try:
            client(cfg).call("DELETE", f"/auth/keys/{cfg['key_id']}")
        except CliError:
            pass
    cfg.pop("api_key", None)
    cfg.pop("key_id", None)
    save_config(cfg)
    print("Signed out; the key was revoked.")


def cmd_whoami(args, cfg):
    me = client(cfg).call("GET", "/auth/me")
    emit(args, me, lambda: print(f"{me.get('email') or 'local mode'} · {me['org_name']} · {me['role']} · {cfg['url']}"))


def cmd_projects(args, cfg):
    ps = client(cfg).call("GET", "/projects")

    def human():
        if not ps:
            print("No projects yet. `concours new --sample` or `concours new --file payments.csv`.")
            return
        rows = [["*" if p["id"] == cfg.get("project") else "", p["id"], p["name"], f"v{p['active_model']['version']}" if p.get("active_model") else "-",
                 p.get("model_status"), money(p.get("money_per_day"))] for p in ps]
        print(table(rows, ["", "id", "name", "model", "status", "caught/day"]))

    emit(args, ps, human)


def cmd_use(args, cfg):
    p = client(cfg).call("GET", f"/projects/{args.id}")
    cfg["project"] = p["id"]
    save_config(cfg)
    print(f"Now using {p['name']} ({p['id']}).")


def cmd_new(args, cfg):
    c = client(cfg)
    if not args.sample and not args.file:
        raise CliError("Choose --sample or --file PATH.")
    p = c.call("POST", "/projects", {"template": "fraud", "name": args.name, "sample": bool(args.sample)})
    if args.file:
        prof = c.upload(f"/projects/{p['id']}/data", Path(args.file))
        print(f"Uploaded {prof['n_rows']:,} payments.")
    cfg["project"] = p["id"]
    save_config(cfg)
    print(f"Created {p['name']} ({p['id']}) and made it current. Next: `concours map`.")


def cmd_delete(args, cfg):
    if not args.yes and input(f"Delete project {args.id} and its files? [y/N] ").strip().lower() != "y":
        print("Kept.")
        return
    client(cfg).call("DELETE", f"/projects/{args.id}")
    if cfg.get("project") == args.id:
        cfg.pop("project")
        save_config(cfg)
    print("Deleted.")


def cmd_upload(args, cfg):
    pid = project_id(args, cfg)
    prof = client(cfg).upload(f"/projects/{pid}/data", Path(args.file))
    print(f"Uploaded {prof['n_rows']:,} payments. Next: `concours map`.")


def cmd_map(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    sch = c.call("GET", f"/projects/{pid}/schema")
    mapping = {f["name"]: f["column"] for f in sch["fields"]}
    for item in args.set or []:
        field, _, col = item.partition("=")
        if field not in FIELDS:
            raise CliError(f"Unknown field {field}. Fields: {', '.join(FIELDS)}")
        mapping[field] = col or None
    rows = [[f, "yes" if f in REQUIRED else "", mapping.get(f) or "-", "" if mapping.get(f) == next((x["suggested"] for x in sch["fields"] if x["name"] == f), None) else "changed"]
            for f in FIELDS]
    if not args.json:
        print(table(rows, ["field", "required", "column", ""]))
    if sch.get("confirmed") and not args.set:
        print("Columns are already confirmed.")
        return
    missing = [f for f in REQUIRED if not mapping.get(f)]
    if missing:
        raise CliError(f"Map the required fields first: {', '.join(missing)} (e.g. --set amount=TX_AMOUNT).")
    if not args.yes and input("Confirm this mapping? [Y/n] ").strip().lower() == "n":
        print("Not confirmed.")
        return
    p = c.call("PUT", f"/projects/{pid}/schema", {"mapping": mapping})
    print(f"Confirmed. Today is {p['as_of']}. Next: `concours settings` (or accept the defaults) and `concours protect`.")


def cmd_settings(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    p = c.call("GET", f"/projects/{pid}")
    st = dict(p.get("fraud_settings") or {"daily_capacity": 200, "review_cost": 10.0, "fraud_fee": 0.0, "label_delay_days": 30})
    for k, v in (("daily_capacity", args.capacity), ("review_cost", args.review_cost), ("fraud_fee", args.fee), ("label_delay_days", args.delay)):
        if v is not None:
            st[k] = v
    p = c.call("PUT", f"/projects/{pid}/fraud-settings", st)
    st = p["fraud_settings"]
    emit(args, st, lambda: print(f"{st['daily_capacity']} cases a day, ${st['review_cost']:.2f} per review, fee ${st['fraud_fee']:.2f}, "
                                 f"{st['label_delay_days']} days to confirm."))


def cmd_protect(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    p = c.call("GET", f"/projects/{pid}")
    if p["stage"] in ("upload", "intake") and p.get("schema_confirmed"):
        c.call("PUT", f"/projects/{pid}/fraud-settings", p.get("fraud_settings") or {})  # accept the shown settings
    rep = c.call("POST", f"/projects/{pid}/protect")

    def human():
        m = rep.get("maturity") or {}
        parts = ", ".join(f"{x['name']} {x['rows']:,}" for x in rep["parts"])
        print(f"Protected: {parts}")
        for f in rep["findings"]:
            if f["severity"] != "info":
                print(f"  [{f['severity']}] {f['column'] or ''}: {f['reason']}")
        if m:
            print(f"  {m['frauds_unconfirmed_in_train']:,} frauds were not yet confirmed at training time; "
                  f"{m['label_delay_days']}-day gap before the test days ({m['holdout_start']} to {m['holdout_end']}).")

    emit(args, rep, human)
    if not args.no_wait:
        print("Building version 1…")
        wait_round(c, pid, quiet=True)
        print(summary(c.call("GET", f"/projects/{pid}")))


def cmd_status(args, cfg):
    p = client(cfg).call("GET", f"/projects/{project_id(args, cfg)}")
    emit(args, p, lambda: print(summary(p)))


def cmd_queue(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    if args.csv:
        data = c.raw("GET", f"/projects/{pid}/queue/download").read()
        Path(args.csv).write_bytes(data)
        print(f"Wrote {args.csv}.")
        return
    q = c.call("GET", f"/projects/{pid}/queue")

    def human():
        print(f"Queue for {q['day']} (model v{q['model_version']}): top {len(q['cases'])} of {q['rows_scored']:,} payments, "
              f"expected loss {money(q['expected_loss_total'])}, {q['labeled']} reviewed")
        rows = [[x["rank"], x["transaction_id"], x["time"][11:], f"{x['amount']:,.2f}", f"{x['risk'] * 100:.0f}%", f"{x['expected_loss']:,.2f}",
                 "; ".join(r["text"] for r in x["reasons"]), x.get("label") or ""] for x in q["cases"][: args.top]]
        print(table(rows, ["#", "transaction", "time", "amount", "risk", "exp. loss", "why", "verdict"]))

    emit(args, q, human)


def cmd_label(args, cfg):
    label = {"fraud": "fraud", "not-fraud": "not_fraud", "not_fraud": "not_fraud", "clear": None}[args.verdict]
    q = client(cfg).call("POST", f"/projects/{project_id(args, cfg)}/queue/{urllib.parse.quote(args.transaction)}/label", {"label": label})
    print(f"Saved. {q['labeled']} of {len(q['cases'])} cases in today's queue reviewed.")


def _gates(sub: dict) -> str:
    g = sub.get("gates") or []
    if not g:
        return ""
    bad = next((x for x in g if not x["passed"]), None)
    return f"{sum(x['passed'] for x in g)}/5" + (f" ({bad['name']}: {bad['line']})" if bad else " all passed")


def cmd_attempts(args, cfg):
    b = client(cfg).call("GET", f"/projects/{project_id(args, cfg)}/arena/leaderboard")

    def human():
        rows = [[s["id"], s["solver"], s["status"], money(s.get("private_score")), _gates(s) or (s.get("error") or "")] for s in b["submissions"]]
        print(table(rows, ["id", "attempt", "status", "caught/day", "gates"]))

    emit(args, b, human)


def cmd_improve(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    body = {"solvers": args.solvers.split(",")} if args.solvers else {}
    ids = c.call("POST", f"/projects/{pid}/arena/run", body)["submission_ids"]
    print(f"Improvement round started: {len(ids)} attempts.")
    if args.no_wait:
        return
    wait_round(c, pid)
    cmd_attempts(argparse.Namespace(json=False, project=pid), cfg)
    print(summary(c.call("GET", f"/projects/{pid}")))


def cmd_versions(args, cfg):
    vs = client(cfg).call("GET", f"/projects/{project_id(args, cfg)}/versions")

    def human():
        rows = [[f"v{v['version']}", v["status"], money(v["private_score"]), v["source"], v["created_at"][:16], _gates(v)] for v in vs]
        print(table(rows, ["version", "status", "caught/day", "source", "created", "gates"]))

    emit(args, vs, human)


def cmd_drift(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    d = c.call("POST", f"/projects/{pid}/drift") if args.check else c.call("GET", f"/projects/{pid}/drift")

    def human():
        if not d:
            print("No health check yet. `concours drift --check` or `concours jump`.")
            return
        print(d["line"])
        for w in d["weeks"]:
            print(f"  {w['week_start']} to {w['week_end']}: {pct(w['share'])} of fraud money caught ({money(w['caught_per_day'])}/day)")
        print("  drift: " + ", ".join(f"{f['name']} PSI {f['psi']:.2f}{' (flagged)' if f['flagged'] else ''}" for f in d["psi"]))

    emit(args, d, human)


def cmd_jump(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    d = c.call("POST", f"/projects/{pid}/clock", {"days": args.days, "auto_round": not args.no_round})
    print(f"Today is now {d['as_of']}. {d['line']}" + (" Improvement round started." if d.get("round_started") else ""))
    if d.get("round_started") and not args.no_wait:
        wait_round(c, pid)
        print(summary(c.call("GET", f"/projects/{pid}")))


def cmd_data(args, cfg):
    rep = client(cfg).call("GET", f"/projects/{project_id(args, cfg)}/protect/report")

    def human():
        m = rep.get("maturity")
        if m:
            print(f"Today {m['as_of']}; train to {m['train_end']}, gap {m['embargo_start']} to {m['embargo_end']}, "
                  f"test {m['holdout_start']} to {m['holdout_end']}; confirmation dates {'simulated' if m['label_time_simulated'] else 'from your file'}.")
        print(f"Kept {len(rep['kept_columns'])} columns; removed {', '.join(rep['dropped_columns']) or 'none'}; scrambled {', '.join(rep['hashed_columns']) or 'none'}.")
        for f in rep["findings"]:
            print(f"  [{f['severity']}] {f['check']} {f['column'] or ''}: {f['reason']}")

    emit(args, rep, human)


def cmd_package(args, cfg):
    c, pid = client(cfg), project_id(args, cfg)
    pk = c.call("POST", f"/projects/{pid}/package")
    print(f"Package {pk['competition_id']}: validation {pk['validation']}")
    for st in pk["steps"]:
        print(f"  {st['status']:8} {st['name']}")
    if args.out:
        Path(args.out).write_bytes(c.raw("GET", f"/projects/{pid}/handoff").read())
        print(f"Wrote {args.out}.")
    if args.repo:
        Path(args.repo).write_bytes(c.raw("GET", f"/projects/{pid}/package/repo").read())
        print(f"Wrote {args.repo}. It holds the private holdout: push it only to a PRIVATE repository.")


def cmd_keys(args, cfg):
    c = client(cfg)
    if args.action == "create":
        k = c.call("POST", "/auth/keys", {"name": args.name or "script"})
        print(f"{k['token']}\n(shown once; store it as CONCOURS_API_KEY)")
    elif args.action == "revoke":
        c.call("DELETE", f"/auth/keys/{args.name}")
        print("Revoked.")
    else:
        ks = c.call("GET", "/auth/keys")
        emit(args, ks, lambda: print(table([[k["id"], k["name"], k["prefix"] + "…", (k.get("last_used_at") or "never")[:16]] for k in ks],
                                           ["id", "name", "key", "last used"])))


# ---------- parser ----------


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="concours", description="Fraud models that keep up with fraudsters, from the terminal.")
    ap.add_argument("--version", action="version", version=f"concours {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, project=True, json_=True):
        p = sub.add_parser(name, help=help_, description=help_)
        p.set_defaults(fn=fn)
        if project:
            p.add_argument("--project", "-p", help="project id (default: the current one)")
        if json_:
            p.add_argument("--json", action="store_true", help="machine-readable output")
        return p

    p = add("login", cmd_login, "Sign in and save an API key", project=False, json_=False)
    p.add_argument("--url", help=f"API address, e.g. https://fraud.example.com/api (default {DEFAULT_URL})")
    p.add_argument("--email")
    p.add_argument("--api-key", help="use an existing key (from Account in the web app) instead of a password")
    add("logout", cmd_logout, "Revoke and forget the saved key", project=False, json_=False)
    add("whoami", cmd_whoami, "Show who you are signed in as", project=False)
    add("projects", cmd_projects, "List projects", project=False)
    p = add("use", cmd_use, "Make a project the current one", project=False, json_=False)
    p.add_argument("id")
    p = add("new", cmd_new, "Create a project", project=False, json_=False)
    p.add_argument("--name")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--sample", action="store_true", help="start from the sample transactions")
    g.add_argument("--file", help="a CSV of payments with a fraud label")
    p = add("delete", cmd_delete, "Delete a project and its files", project=False, json_=False)
    p.add_argument("id")
    p.add_argument("--yes", "-y", action="store_true")
    p = add("upload", cmd_upload, "Upload transactions (replaces the current file)", json_=False)
    p.add_argument("file")
    p = add("map", cmd_map, "Show and confirm the column mapping")
    p.add_argument("--set", action="append", metavar="FIELD=COLUMN", help=f"override one field ({', '.join(FIELDS)})")
    p.add_argument("--yes", "-y", action="store_true", help="confirm without asking")
    p = add("settings", cmd_settings, "The three questions: capacity, costs, confirmation delay")
    p.add_argument("--capacity", type=int, help="cases your team reviews per day")
    p.add_argument("--review-cost", type=float, help="cost of one review")
    p.add_argument("--fee", type=float, help="cost of a missed fraud on top of its amount")
    p.add_argument("--delay", type=int, help="days until fraud is usually confirmed")
    p = add("protect", cmd_protect, "Protect the data, then build version 1")
    p.add_argument("--no-wait", action="store_true")
    add("status", cmd_status, "Show the project's model, money per day and health")
    p = add("queue", cmd_queue, "Today's review queue")
    p.add_argument("--top", type=int, default=20, help="rows to print (default 20)")
    p.add_argument("--csv", help="write the whole queue to this CSV file")
    p = add("label", cmd_label, "Record an analyst verdict", json_=False)
    p.add_argument("transaction")
    p.add_argument("verdict", choices=["fraud", "not-fraud", "not_fraud", "clear"])
    p = add("improve", cmd_improve, "Run an improvement round and show the gates")
    p.add_argument("--solvers", help="comma-separated local solvers (default: the fraud round)")
    p.add_argument("--no-wait", action="store_true")
    add("attempts", cmd_attempts, "Improvement attempts with their gate results")
    add("versions", cmd_versions, "Model versions")
    p = add("drift", cmd_drift, "Weekly health and drift")
    p.add_argument("--check", action="store_true", help="run the check now")
    p = add("jump", cmd_jump, "Move the simulated clock forward (sample data)", json_=False)
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--no-round", action="store_true", help="do not start an improvement round when slipping")
    p.add_argument("--no-wait", action="store_true")
    add("data", cmd_data, "Protection report and late labels")
    p = add("package", cmd_package, "Package for Apex and validate", json_=False)
    p.add_argument("--out", help="also download the handoff zip here")
    p.add_argument("--repo", help="also download the private competition repo (holdout included) here")
    p = add("keys", cmd_keys, "API keys: list, create NAME, revoke ID", project=False)
    p.add_argument("action", nargs="?", default="list", choices=["list", "create", "revoke"])
    p.add_argument("name", nargs="?")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    cfg = load_config()
    try:
        args.fn(args, cfg)
    except CliError as e:
        print(f"concours: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
