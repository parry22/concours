"""Brief backend. One FastAPI app, six service modules, SQLite + workspace/ on disk."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import MAX_UPLOAD_MB, project_dir
from app.db import get_session, init_db
from app.models import (
    DataProfile,
    ProblemSpec,
    ProjectCreate,
    ProjectOut,
    ProjectRow,
    ProtectReport,
)
from app.packager.profile import profile_dataframe, read_csv
from app.packager.protect import protect
from app.templates import dataset_path, list_templates, load_defaults, spec_from_defaults

app = FastAPI(title="Brief", version="0.1.0", description="Turn a spreadsheet prediction problem into a protected, Apex-ready competition.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STAGES = ["upload", "intake", "protect", "arena", "serve", "launch"]


@app.on_event("startup")
def _startup() -> None:
    init_db()


def get_project(project_id: str, s: Session) -> ProjectRow:
    row = s.get(ProjectRow, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    return row


def advance(row: ProjectRow, stage: str) -> None:
    if STAGES.index(stage) > STAGES.index(row.stage):
        row.stage = stage


# ---------- templates and projects ----------


@app.get("/templates")
def templates() -> list[dict]:
    return list_templates()


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(s: Session = Depends(get_session)) -> list[ProjectOut]:
    rows = s.exec(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
    return [r.to_out() for r in rows]


@app.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, s: Session = Depends(get_session)) -> ProjectOut:
    cfg = load_defaults(body.template) if body.template != "custom" else None
    row = ProjectRow(name=body.name or (cfg["name"] if cfg else "New problem"), template=body.template)
    s.add(row)
    s.commit()
    s.refresh(row)
    if body.template != "custom":
        p = dataset_path(body.template)
        if p:
            _ingest_csv(row, p)
            s.add(row)
            s.commit()
            s.refresh(row)
    return row.to_out()


@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project_out(project_id: str, s: Session = Depends(get_session)) -> ProjectOut:
    return get_project(project_id, s).to_out()


@app.delete("/projects/{project_id}")
def delete_project(project_id: str, s: Session = Depends(get_session)) -> dict:
    row = get_project(project_id, s)
    s.delete(row)
    s.commit()
    shutil.rmtree(project_dir(project_id), ignore_errors=True)
    return {"ok": True}


# ---------- data ----------


def _ingest_csv(row: ProjectRow, src: Path) -> DataProfile:
    dst = project_dir(row.id) / "dataset.csv"
    if src != dst:
        shutil.copyfile(src, dst)
    df = read_csv(dst)
    prof = profile_dataframe(df)
    row.profile_json = prof.model_dump_json()
    if row.spec_json is None and row.template != "custom":
        row.set_spec(spec_from_defaults(row.template))
    advance(row, "intake")
    return prof


@app.post("/projects/{project_id}/data", response_model=DataProfile)
async def upload_data(project_id: str, file: UploadFile = File(...), s: Session = Depends(get_session)) -> DataProfile:
    row = get_project(project_id, s)
    dst = project_dir(project_id) / "dataset.csv"
    size = 0
    with open(dst, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB << 20:
                raise HTTPException(413, f"CSV larger than {MAX_UPLOAD_MB} MB")
            f.write(chunk)
    try:
        prof = _ingest_csv(row, dst)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not read CSV: {e}") from e
    # a new upload invalidates downstream state
    row.protect_json = None
    row.stage = "intake"
    s.add(row)
    s.commit()
    return prof


@app.get("/projects/{project_id}/data/profile", response_model=DataProfile)
def get_profile(project_id: str, s: Session = Depends(get_session)) -> DataProfile:
    row = get_project(project_id, s)
    prof = row.profile()
    if not prof:
        raise HTTPException(409, "upload a CSV first")
    return prof


# ---------- spec ----------


@app.put("/projects/{project_id}/spec", response_model=ProjectOut)
def put_spec(project_id: str, spec: ProblemSpec, s: Session = Depends(get_session)) -> ProjectOut:
    row = get_project(project_id, s)
    prof = row.profile()
    if prof and spec.target_column not in [c.name for c in prof.columns]:
        raise HTTPException(400, f"target column {spec.target_column} is not in the data")
    row.set_spec(spec)
    advance(row, "protect")
    s.add(row)
    s.commit()
    return row.to_out()


# ---------- protect ----------


@app.post("/projects/{project_id}/protect", response_model=ProtectReport)
def run_protect(project_id: str, s: Session = Depends(get_session)) -> ProtectReport:
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec:
        raise HTTPException(409, "confirm the problem spec first")
    df = read_csv(project_dir(project_id) / "dataset.csv")
    if spec.target_column not in df.columns:
        raise HTTPException(400, f"target column {spec.target_column} is not in the data")
    report, _ = protect(df, spec, project_dir(project_id) / "protected")
    row.protect_json = report.model_dump_json()
    advance(row, "arena")
    s.add(row)
    s.commit()
    return report


@app.get("/projects/{project_id}/protect/report", response_model=ProtectReport)
def protect_report(project_id: str, s: Session = Depends(get_session)) -> ProtectReport:
    row = get_project(project_id, s)
    rep = row.protect()
    if not rep:
        raise HTTPException(409, "run protection first")
    return rep


# ---------- arena ----------

import asyncio  # noqa: E402

from sse_starlette.sse import EventSourceResponse  # noqa: E402

from app.arena import events, leaderboard, runner, service as arena  # noqa: E402
from app.models import LeaderboardOut, SubmissionRow  # noqa: E402


@app.on_event("startup")
async def _loop() -> None:
    events.set_loop(asyncio.get_running_loop())


from pydantic import BaseModel  # noqa: E402


class ArenaRunRequest(BaseModel):
    solvers: list[str] | None = None
    replay: bool = True
    rebuild: bool = False


@app.get("/arena/solvers")
def list_solvers() -> list[dict]:
    out = [{"name": n, "label": n.replace("_", " "), "local": True} for n in runner.SOLVERS]
    out += [{"name": f"agent_solver_{i}", "label": f"Agent solver, attempt {i}", "local": True, "agent": True} for i in (1, 2, 3)]
    return out


@app.get("/arena/docker")
def docker_status() -> dict:
    ok, info = runner.docker_available()
    return {"available": ok, "info": info}


@app.post("/projects/{project_id}/arena/run")
def arena_run(project_id: str, body: ArenaRunRequest | None = None, s: Session = Depends(get_session)) -> dict:
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    body = body or ArenaRunRequest()
    solvers = body.solvers or runner.SOLVERS
    unknown = [x for x in solvers if x not in runner.SOLVERS]
    if unknown:
        raise HTTPException(400, f"unknown solvers {unknown}")
    try:
        ids = arena.start_run(project_id, solvers, replay=body.replay, rebuild=body.rebuild)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    advance(row, "arena")
    s.add(row)
    s.commit()
    return {"submission_ids": ids}


@app.get("/projects/{project_id}/arena/leaderboard", response_model=LeaderboardOut)
def arena_leaderboard(project_id: str, s: Session = Depends(get_session)) -> LeaderboardOut:
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec:
        raise HTTPException(409, "confirm the problem spec first")
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
    return leaderboard.build(project_id, subs, spec, row.finalized)


@app.get("/projects/{project_id}/arena/stream")
async def arena_stream(project_id: str):
    q = events.subscribe(project_id)

    async def gen():
        try:
            yield {"event": "connected", "data": "{}"}
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=15)
                    yield msg
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            events.unsubscribe(project_id, q)

    return EventSourceResponse(gen())


@app.post("/projects/{project_id}/arena/finalize", response_model=LeaderboardOut)
def arena_finalize(project_id: str, s: Session = Depends(get_session)) -> LeaderboardOut:
    get_project(project_id, s)
    try:
        arena.finalize(project_id)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    s.expire_all()
    return arena_leaderboard(project_id, s)


@app.get("/projects/{project_id}/arena/status")
def arena_status(project_id: str) -> dict:
    from app.arena import agent_solver as _ag  # noqa: PLC0415

    return {"running": arena.is_running(project_id) or _ag.is_running(project_id)}


# ---------- package, handoff, serving ----------

from fastapi.responses import FileResponse  # noqa: E402

from app.apex_builder import generator, validate  # noqa: E402
from app.handoff.build import build_zip  # noqa: E402
from app.models import PackageOut  # noqa: E402
from app.serving.score import score_csv  # noqa: E402


@app.post("/projects/{project_id}/package", response_model=PackageOut)
def build_package(project_id: str, s: Session = Depends(get_session)) -> PackageOut:
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the arena run to finish")
    if runner.image_id(project_id, "player") is None or runner.image_id(project_id, "referee") is None:
        # arena replayed cached scores, so the images for this project were never built; build them now
        from app.arena.stage import stage  # noqa: PLC0415

        stage(project_id, row.spec())
        runner.build_images(project_id, lambda line: None)
    comp, _ = generator.generate(project_id)
    steps = [validate.preflight(comp), validate.screen(comp), validate.local_run(project_id)]
    status = validate.overall(steps)
    # regenerate HANDOFF.md / ONBOARDING_ISSUE.md with the validation outcome filled in
    comp, _ = generator.generate(project_id, validation={
        "preflight": steps[0].status, "local_run": steps[2].status, "local_run_detail": steps[2].log[:160]})
    out = PackageOut(competition_dir=str(comp), competition_id=generator.competition_id(row), validation=status,  # type: ignore[arg-type]
                     steps=steps, files=generator.file_list(comp))
    row.apex_validation = status
    row.package_json = out.model_dump_json()
    s.add(row)
    s.commit()
    return out


@app.get("/projects/{project_id}/package", response_model=PackageOut)
def get_package(project_id: str, s: Session = Depends(get_session)) -> PackageOut:
    row = get_project(project_id, s)
    if not row.package_json:
        raise HTTPException(409, "build the package first")
    return PackageOut.model_validate_json(row.package_json)


@app.get("/projects/{project_id}/package/file")
def package_file(project_id: str, path: str, s: Session = Depends(get_session)) -> dict:
    get_project(project_id, s)
    comp = generator.competition_dir(project_id).resolve()
    p = (comp / path).resolve()
    if not str(p).startswith(str(comp)) or not p.is_file():
        raise HTTPException(404, "no such file")
    if p.suffix in (".csv",) and p.stat().st_size > 200_000:
        return {"path": path, "content": p.read_text()[:4000] + "\n... (truncated)"}
    try:
        return {"path": path, "content": p.read_text()[:60_000]}
    except UnicodeDecodeError:
        return {"path": path, "content": "(binary)"}


@app.get("/projects/{project_id}/handoff")
def handoff(project_id: str, s: Session = Depends(get_session)):
    row = get_project(project_id, s)
    if not row.package_json:
        raise HTTPException(409, "build the package first")
    path = build_zip(project_id)
    advance(row, "launch")
    s.add(row)
    s.commit()
    return FileResponse(path, media_type="application/zip", filename=f"brief-handoff-{generator.competition_id(row)}.zip")


@app.post("/projects/{project_id}/score")
async def score(project_id: str, file: UploadFile = File(...), solver: str | None = None, s: Session = Depends(get_session)) -> dict:
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec or not row.protect():
        raise HTTPException(409, "run protection first")
    chosen = solver or row.winner_solver or "lgbm_tuned"
    if chosen not in runner.SOLVERS:
        raise HTTPException(400, f"unknown solver {chosen}")
    sdir = project_dir(project_id) / "serving"
    sdir.mkdir(exist_ok=True)
    src, dst = sdir / "input.csv", sdir / "scored.csv"
    with open(src, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    try:
        result = score_csv(project_id, chosen, spec, src, dst)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    advance(row, "serve")
    s.add(row)
    s.commit()
    result["download"] = f"/projects/{project_id}/score/download"
    return result


@app.get("/projects/{project_id}/score/download")
def score_download(project_id: str, s: Session = Depends(get_session)):
    get_project(project_id, s)
    p = project_dir(project_id) / "serving" / "scored.csv"
    if not p.exists():
        raise HTTPException(404, "score a CSV first")
    return FileResponse(p, media_type="text/csv", filename="scored.csv")


@app.get("/projects/{project_id}/sample-csv")
def sample_csv(project_id: str, n: int = 2000, s: Session = Depends(get_session)):
    """A fresh CSV for the demo: the newest rows of the holdout, without labels."""
    import pandas as pd  # noqa: PLC0415

    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    src = project_dir(project_id) / "protected" / "holdout.csv"
    p = project_dir(project_id) / "serving" / "sample_new_rows.csv"
    p.parent.mkdir(exist_ok=True)
    pd.read_csv(src).tail(n).to_csv(p, index=False)
    return FileResponse(p, media_type="text/csv", filename="new_rows.csv")


# ---------- intake ----------

from app.intake.agent import IntakeAgent  # noqa: E402
from app.models import IntakeMessage, IntakeRequest, IntakeResponse  # noqa: E402

_agent = IntakeAgent()


@app.post("/projects/{project_id}/intake", response_model=IntakeResponse)
async def intake(project_id: str, body: IntakeRequest, s: Session = Depends(get_session)) -> IntakeResponse:
    row = get_project(project_id, s)
    prof = row.profile()
    if not prof:
        raise HTTPException(409, "upload a CSV first")
    resp = await _agent.turn(template=row.template, profile=prof, spec=row.spec(), history=row.intake(), user_message=body.message)
    row.set_intake(resp.history)
    if resp.spec:
        row.set_spec(resp.spec)
    if resp.done:
        advance(row, "protect")
    s.add(row)
    s.commit()
    return resp


@app.get("/projects/{project_id}/intake", response_model=list[IntakeMessage])
def intake_history(project_id: str, s: Session = Depends(get_session)) -> list[IntakeMessage]:
    return get_project(project_id, s).intake()


@app.delete("/projects/{project_id}/intake")
def intake_reset(project_id: str, s: Session = Depends(get_session)) -> dict:
    row = get_project(project_id, s)
    row.set_intake([])
    s.add(row)
    s.commit()
    return {"ok": True}


@app.get("/intake/status")
async def intake_status() -> dict:
    from app import config, llm  # noqa: PLC0415

    prov = llm.provider()
    logged_in = await llm.cli_logged_in() if prov == "cli" else None
    return {"offline": config.OFFLINE or (prov == "cli" and not logged_in), "model": config.INTAKE_MODEL,
            "has_key": bool(config.ANTHROPIC_API_KEY), "provider": prov, "cli_logged_in": logged_in,
            "hint": None if prov != "cli" or logged_in else "Run `claude auth login` in a terminal once to use your Claude subscription."}


# ---------- agent solver (stretch) ----------

from app.arena import agent_solver  # noqa: E402


@app.post("/projects/{project_id}/arena/agent")
def arena_agent(project_id: str, replay: bool = True, s: Session = Depends(get_session)) -> dict:
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the local solver run to finish")
    from app import llm  # noqa: PLC0415

    if llm.provider() == "none":
        raise HTTPException(409, "no model available: set ANTHROPIC_API_KEY or run `claude auth login`")
    try:
        agent_solver.start(project_id, replay=replay)
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    return {"started": True, "max_attempts": agent_solver.MAX_ATTEMPTS}


@app.get("/projects/{project_id}/arena/agent/status")
def arena_agent_status(project_id: str) -> dict:
    return {"running": agent_solver.is_running(project_id)}
