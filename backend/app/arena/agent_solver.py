"""agent_solver: an LLM writes feature engineering + LightGBM code from a template, iterating up to 3 times on
public leaderboard feedback. The model sees only the schema (column names, dtypes, stats), transform.json, the
SolverBase API and the baseline. It never sees rows.

Attempts and their scores are cached under .cache/arena/agent/<data_hash>/ so `make demo` replays them.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import threading
import time
from pathlib import Path

from sqlmodel import select

from app import config, llm
from app.arena import events, leaderboard, runner
from app.arena.stage import data_hash, round_config, stage
from app.config import SOLVERS_DIR, project_dir
from app.db import session
from app.models import ProblemSpec, ProjectRow, SubmissionRow
from app.shared.metrics import METRIC_NAMES

MAX_ATTEMPTS = 3
FORBIDDEN_MODULES = {"socket", "subprocess", "requests", "urllib", "http", "os", "sys", "shutil", "pathlib", "importlib", "ctypes", "multiprocessing", "pickle"}
ALLOWED_TOP = {"numpy", "pandas", "sklearn", "lightgbm", "xgboost", "common", "math", "typing", "__future__", "collections", "itertools", "functools", "re", "json", "datetime"}

SYSTEM = """You are a solver in Concours's local improvement round: a careful tabular ML engineer.
You write ONE Python file, submission.py, that defines `class Solver(SolverBase)` with `fit(self, X, y)` and `predict_proba(self, X)`.
Rules:
- `from common.base import SolverBase, FeaturePrep` is available. SolverBase.__init__(transform) builds self.prep = FeaturePrep(transform, history=self.history).
  Set the class attribute `history = True` to get per-entity history features (previous count, previous positives, 28-day window, amount ratio) computed from past rows only.
- You may override `fit_frame(self, train)` / `score_frame(self, df)` to add your own feature engineering on top of self.prep, but keep the same signatures and keep every feature computable from a single batch of rows plus state learned in fit.
- Allowed imports: numpy, pandas, sklearn, lightgbm, xgboost, math, collections, itertools, functools, re, json, datetime, typing, common. Nothing else. No file, network or process access. No printing.
- Training must finish in under 4 minutes on 2 CPUs with 2 GB RAM. Set n_jobs=2 on tree models.
- Scores must be floats where higher means more likely positive. No NaN.
- Reply with the complete file inside one ```python fenced block and at most three sentences before it explaining the idea. Nothing after the block.
"""


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def extract_code(text: str) -> str | None:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    code = m.group(1) if m else (text if "class Solver" in text else None)
    return code.strip() + "\n" if code else None


def screen_code(code: str) -> str | None:
    """Return a reason if the code is not acceptable, else None. Mirrors the spirit of Apex's AST screen."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax error: {e}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for n in names:
                top = n.split(".")[0]
                if top in FORBIDDEN_MODULES or top not in ALLOWED_TOP:
                    return f"import of `{n}` is not allowed"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("exec", "eval", "open", "__import__", "compile"):
            return f"call to `{node.func.id}` is not allowed"
        if isinstance(node, ast.Attribute) and node.attr in ("__subclasses__", "__globals__", "__builtins__"):
            return f"attribute `{node.attr}` is not allowed"
    if "class Solver" not in code:
        return "no `class Solver` defined"
    return None


def _schema_text(row: ProjectRow, spec: ProblemSpec) -> str:
    prof = row.profile()
    protected = project_dir(row.id) / "protected"
    transform = json.loads((protected / "transform.json").read_text())
    kept = set(transform["kept"])
    lines = [f"Task: {spec.business_template} prediction. Target `{spec.target_column}` arrives as the `label` column (1 = positive) in train only.",
             f"Metric: {METRIC_NAMES.get(spec.primary_metric, spec.primary_metric)} {spec.metric_params}. Higher is better.",
             f"Time column: {spec.time_column or 'none'}. Hidden rows come after training rows in time." if spec.time_column else "No time column; random split.",
             f"Training rows: about {[p.rows for p in row.protect().parts if p.name == 'train'][0]}.",
             "Columns the solver receives (name, dtype, null %, unique ratio, min, max):"]
    for c in prof.columns:
        if c.name in kept:
            lines.append(f"  - {c.name}: {c.dtype}, null {c.null_pct}%, unique ratio {c.unique_ratio}, min {c.min}, max {c.max}")
    lines.append(f"Dropped by data protection (never present): {transform['dropped']}")
    return "\n".join(lines)


def _prompt(row: ProjectRow, spec: ProblemSpec, attempts: list[dict]) -> list[dict[str, str]]:
    base_src = (SOLVERS_DIR / "common" / "base.py").read_text()
    baseline_src = (SOLVERS_DIR / "baseline_logreg" / "submission.py").read_text()
    msg = [_schema_text(row, spec), "", "### common/base.py (read only)", "```python", base_src, "```", "", "### baseline submission.py", "```python", baseline_src, "```"]
    if attempts:
        msg.append("")
        msg.append("### Your previous attempts and their public leaderboard scores")
        for a in attempts:
            msg.append(f"Attempt {a['n']}: public score {a.get('public_score')}" + (f", failed: {a['error']}" if a.get("error") else ""))
            msg.append("```python\n" + a["code"] + "```")
        msg.append("Improve on the best attempt. Change one or two things with a clear rationale; do not rewrite everything.")
    else:
        msg.append("")
        msg.append("Write your first attempt. Think about which engineered features capture the patterns a fraud or churn signal usually has, then pick a gradient boosting model.")
    return [{"role": "user", "content": "\n".join(msg)}]


def _cache_dir(dh: str) -> Path:
    return config.ARENA_CACHE_DIR / "agent" / dh


def run_agent(project_id: str, *, replay: bool = True) -> None:
    """Blocking. Runs up to MAX_ATTEMPTS attempts, recording each as a SubmissionRow and publishing SSE events."""
    log = lambda line: events.publish(project_id, "log", {"line": line})  # noqa: E731
    with session() as s:
        row = s.get(ProjectRow, project_id)
        spec = row.spec()
    dh = data_hash(project_id)
    cache = _cache_dir(dh)
    cached_attempts = sorted(cache.glob("attempt_*.json")) if replay and cache.exists() else []
    if not runner.images_current(project_id, dh):
        log("agent_solver: building player and referee images")
        stage(project_id, spec)
        runner.build_images(project_id, lambda line: None, data=dh)
    cfg = round_config(spec)
    attempts: list[dict] = []
    work = project_dir(project_id) / "agent_solver"
    work.mkdir(exist_ok=True)
    for n in range(1, MAX_ATTEMPTS + 1):
        name = f"agent_solver_{n}"
        with session() as s:
            sub = SubmissionRow(project_id=project_id, solver=name, status="running", data_hash=f"{dh}:agent{n}", logs_path="")
            s.add(sub)
            s.commit()
            s.refresh(sub)
            sid = sub.id
        events.publish(project_id, "submission_started", {"id": sid, "solver": name, "cached": bool(cached_attempts)})
        replayed = None
        if cached_attempts and len(cached_attempts) >= n:
            replayed = json.loads(cached_attempts[n - 1].read_text())
            code, note = replayed["code"], replayed.get("note", "")
            log(f"{name}: replaying a saved attempt (same data)")
            time.sleep(1.5)
        else:
            log(f"{name}: asking the model for attempt {n} of {MAX_ATTEMPTS} (schema only, no rows)")
            try:
                text = _complete(_prompt(row, spec, attempts))
            except Exception as e:  # noqa: BLE001
                _fail(sid, f"model call failed: {e}", project_id, spec, log)
                break
            code = extract_code(text)
            note = text.split("```")[0].strip()[:300]
            if not code:
                _fail(sid, "model reply had no code block", project_id, spec, log)
                attempts.append({"n": n, "code": "", "error": "no code block"})
                continue
        reason = screen_code(code)
        if reason:
            log(f"{name}: rejected by the code screen ({reason})")
            _fail(sid, f"code screen: {reason}", project_id, spec, log)
            attempts.append({"n": n, "code": code, "error": reason})
            continue
        sub_dir = work / f"attempt_{n}"
        sub_dir.mkdir(exist_ok=True)
        (sub_dir / "submission.py").write_text(code)
        if note:
            log(f"{name}: {note}")
        if replayed:
            res_ok, result, error, seconds, logs_dir = True, replayed["result"], None, replayed.get("eval_seconds", 0), Path(replayed.get("logs_path", ""))
        else:
            log(f"{name}: running in Docker ({runner.SOLVER_CPUS} CPUs, {runner.SOLVER_MEM}, {runner.SOLVER_TIMEOUT_S}s limit)")
            r = runner.run_submission(project_id, sid, name, cfg, submission_path=sub_dir / "submission.py")
            res_ok, result, error, seconds, logs_dir = r.ok, r.result, r.error, r.seconds, r.logs_dir
        with session() as s:
            sub = s.get(SubmissionRow, sid)
            sub.logs_path = str(logs_dir)
            sub.eval_seconds = round(float(seconds), 1)
            if res_ok and result:
                md = result.get("metadata", {})
                sub.public_score = md.get("public_score")
                sub.private_score = result["raw_scores"][0]
                sec = md.get("secondary") or {}
                sub.secondary_public, sub.secondary_private = sec.get("public"), sec.get("private")
                sub.result_json = json.dumps(result)
                sub.status = "scored"
                if result.get("terminal_reason") == "player_error":
                    sub.status, sub.error = "failed", md.get("error", "player error")
            else:
                sub.status, sub.error = "failed", error
            s.add(sub)
            s.commit()
            out = leaderboard.to_out(sub, False)
        attempts.append({"n": n, "code": code, "public_score": out.public_score, "error": out.error})
        if not replayed and out.status == "scored":
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"attempt_{n}.json").write_text(json.dumps({"code": code, "note": note, "result": result, "eval_seconds": seconds, "logs_path": str(logs_dir)}))
        log(f"{name}: {out.status}" + (f", public score {out.public_score:.4f}" if out.public_score is not None else "") + (f" ({out.error})" if out.error else ""))
        events.publish(project_id, "submission_scored", out.model_dump())
        if out.status == "scored":
            from app.arena.service import promote_after_score  # noqa: PLC0415 - service imports this module

            promote_after_score(project_id, sid, spec)
        _emit_board(project_id, spec)
    events.publish(project_id, "run_complete", {"agent": True, "purpose": "contest"})


def _complete(messages: list[dict[str, str]]) -> str:
    import asyncio  # noqa: PLC0415

    async def go():
        if llm.provider() == "api":
            from anthropic import AsyncAnthropic  # noqa: PLC0415

            return await llm.complete_api(AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY), SYSTEM, messages, model=config.INTAKE_MODEL)
        if llm.provider() == "cli":
            return await llm.complete_cli(SYSTEM, messages, model=config.INTAKE_MODEL, timeout_s=300)
        raise RuntimeError("no LLM provider: set ANTHROPIC_API_KEY or run `claude auth login`")

    return asyncio.run(go())


def _fail(sid: str, error: str, project_id: str, spec: ProblemSpec, log) -> None:
    with session() as s:
        sub = s.get(SubmissionRow, sid)
        sub.status, sub.error = "failed", error[:500]
        s.add(sub)
        s.commit()
        out = leaderboard.to_out(sub, False)
    log(f"{sub.solver}: failed ({error[:160]})")
    events.publish(project_id, "submission_scored", out.model_dump())
    _emit_board(project_id, spec)


def _emit_board(project_id: str, spec: ProblemSpec) -> None:
    from app.arena.service import build_board  # noqa: PLC0415 - service imports this module

    with session() as s:
        row = s.get(ProjectRow, project_id)
        board = build_board(s, project_id, spec, row)
    events.publish(project_id, "leaderboard_updated", board.model_dump())


_threads: dict[str, threading.Thread] = {}


def start(project_id: str, *, replay: bool = True) -> None:
    t = _threads.get(project_id)
    if t and t.is_alive():
        raise RuntimeError("the agent solver is already running")
    t = threading.Thread(target=run_agent, args=(project_id,), kwargs={"replay": replay}, daemon=True)
    _threads[project_id] = t
    t.start()


def is_running(project_id: str) -> bool:
    t = _threads.get(project_id)
    return bool(t and t.is_alive())
