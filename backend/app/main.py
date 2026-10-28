"""Concours backend. One FastAPI app, SQLite + workspace/ on disk.

Flow: upload, intake, protect (which builds model version 1), model (lists, performance watch), improve
(contest rounds and promotions), launch (Apex handoff)."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import BASELINE_SOLVERS, MAX_UPLOAD_MB, project_dir
from app.db import get_session, init_db
from app.models import (
    DataProfile,
    HealthOut,
    ListOut,
    ModelVersionOut,
    PlanOut,
    ProblemSpec,
    ProjectCreate,
    ProjectOut,
    ProjectRow,
    ProjectSettingsIn,
    ProtectReport,
    ValueParamsIn,
    ValueReport,
)
from app.models_registry import health as health_mod
from app.models_registry import lists as lists_mod
from app.models_registry import plan as plan_mod
from app.models_registry import promotion
from app.packager.profile import profile_dataframe, read_csv
from app.value import params as value_params_mod
from app.value import service as value_service
from app.packager.protect import protect
from app.templates import dataset_path, list_templates, load_defaults, spec_from_defaults

app = FastAPI(title="Concours", version="0.2.0", description="A working model today. A global network of solvers keeps improving it.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

STAGES = ["upload", "intake", "protect", "model", "improve", "launch"]


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
    row.updated_at = datetime.now(timezone.utc)


def project_out(row: ProjectRow, s: Session) -> ProjectOut:
    from app.arena import service as _arena  # noqa: PLC0415

    return row.to_out(promotion.versions_out(s, row.id, row.spec()), running=_arena.is_running(row.id))


# ---------- templates and projects ----------


@app.get("/templates")
def templates() -> list[dict]:
    return list_templates()


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(s: Session = Depends(get_session)) -> list[ProjectOut]:
    rows = s.exec(select(ProjectRow).order_by(ProjectRow.created_at.desc())).all()
    return [project_out(r, s) for r in rows]


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
    return project_out(row, s)


@app.get("/projects/{project_id}", response_model=ProjectOut)
def get_project_out(project_id: str, s: Session = Depends(get_session)) -> ProjectOut:
    return project_out(get_project(project_id, s), s)


@app.put("/projects/{project_id}/settings", response_model=ProjectOut)
def put_settings(project_id: str, body: ProjectSettingsIn, s: Session = Depends(get_session)) -> ProjectOut:
    """Refresh preference (stored only, no scheduler yet), promotion margin and drift threshold."""
    row = get_project(project_id, s)
    if body.refresh_daily is not None:
        row.refresh_daily = body.refresh_daily
    if body.min_improvement is not None:
        if not 0 <= body.min_improvement <= 1:
            raise HTTPException(400, "min_improvement must be between 0 and 1")
        row.min_improvement = body.min_improvement
    if body.drift_threshold is not None:
        if not 0 <= body.drift_threshold <= 1:
            raise HTTPException(400, "drift_threshold must be between 0 and 1")
        row.drift_threshold = body.drift_threshold
    row.updated_at = datetime.now(timezone.utc)
    s.add(row)
    s.commit()
    return project_out(row, s)


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
    cfg = load_defaults(row.template) if row.template != "custom" else None
    prof = profile_dataframe(df, target=cfg.get("target_column") if cfg else None, positive=cfg.get("positive_label") if cfg else None)
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
    return project_out(row, s)


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
    # a new protected split invalidates the versions built on the old one
    for v in promotion.versions_for(s, project_id):
        s.delete(v)
    row.active_model_id = None
    row.finalized = False
    row.health, row.health_json = "unknown", None
    row.stage = "protect"
    row.updated_at = datetime.now(timezone.utc)
    s.add(row)
    s.commit()
    # version 1 starts now: the baseline solvers run (replayed from cache when the data is known)
    try:
        arena.start_run(project_id, list(BASELINE_SOLVERS), replay=True, purpose="baseline")
    except RuntimeError:
        pass  # a run is in progress; after_run builds v1 when it ends
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
        ids = arena.start_run(project_id, solvers, replay=body.replay, rebuild=body.rebuild, purpose="contest")
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e
    advance(row, "improve")
    s.add(row)
    s.commit()
    return {"submission_ids": ids}


@app.get("/projects/{project_id}/arena/leaderboard", response_model=LeaderboardOut)
def arena_leaderboard(project_id: str, s: Session = Depends(get_session)) -> LeaderboardOut:
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec:
        raise HTTPException(409, "confirm the problem spec first")
    return arena.build_board(s, project_id, spec, row)


@app.get("/projects/{project_id}/versions", response_model=list[ModelVersionOut])
def versions(project_id: str, s: Session = Depends(get_session)) -> list[ModelVersionOut]:
    row = get_project(project_id, s)
    return promotion.versions_out(s, project_id, row.spec())


# ---------- value model ----------


@app.get("/projects/{project_id}/value", response_model=ValueReport)
def value_report(project_id: str, solver: str | None = None, s: Session = Depends(get_session)) -> ValueReport:
    """Money per month for the leader (or `solver`): operating points, range, curve, sensitivity."""
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec:
        raise HTTPException(409, "confirm the problem spec first")
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id).order_by(SubmissionRow.created_at)).all()
    v1 = next((v for v in promotion.versions_for(s, project_id) if v.version == 1), None)
    rep = value_service.report_for(project_id, spec, subs, solver, finalized=True, profile=row.profile(), protect=row.protect(), allow_refit=True,
                                   baseline_solver=v1.solver_name if v1 else "baseline_logreg")
    if rep is None:
        raise HTTPException(409, "no scored submission to price yet")
    return rep


@app.put("/projects/{project_id}/value/params", response_model=ValueReport)
def value_params(project_id: str, body: ValueParamsIn, solver: str | None = None, s: Session = Depends(get_session)) -> ValueReport:
    """Set or clear user overrides for the value parameters. Stored on the spec as `economics`."""
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec:
        raise HTTPException(409, "confirm the problem spec first")
    econ = value_params_mod.normalize_economics(spec.economics, spec.business_template)
    for k, v in body.model_dump().items():
        if v is None:
            econ.pop(k, None)
        else:
            econ[k] = float(v)
    row.set_spec(spec.model_copy(update={"economics": econ or None}))
    s.add(row)
    s.commit()
    return value_report(project_id, solver, s)


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
from app.models import ListRow, PackageOut  # noqa: E402


@app.post("/projects/{project_id}/package", response_model=PackageOut)
def build_package(project_id: str, s: Session = Depends(get_session)) -> PackageOut:
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the arena run to finish")
    if runner.image_id(project_id, "player") is None or runner.image_id(project_id, "referee") is None:
        # cached replays never built this project's images; build them now
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
    advance(row, "launch")
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
    return FileResponse(path, media_type="application/zip", filename=f"concours-handoff-{generator.competition_id(row)}.zip")


# ---------- lists (batch delivery) and the performance watch ----------


def _active_version(row: ProjectRow, s: Session):
    v = promotion.active_version(s, row.id)
    if v is None:
        raise HTTPException(409, "no model yet: protect the data first and version 1 is built automatically")
    return v


async def _save_upload(file: UploadFile, dst: Path) -> None:
    with open(dst, "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)


def _sample_rows(row: ProjectRow, n: int, *, labeled: bool, degrade: bool) -> Path:
    """Fresh rows for the demo: the newest holdout rows, with or without labels, optionally degraded."""
    import pandas as pd  # noqa: PLC0415

    spec = row.spec()
    src = project_dir(row.id) / "protected" / "holdout.csv"
    df = pd.read_csv(src).tail(n).reset_index(drop=True)
    if labeled:
        y = pd.read_csv(project_dir(row.id) / "protected" / "holdout_labels.csv")["label"].tail(n).to_numpy()
        pos = spec.positive_label if spec.positive_label is not None else 1
        neg = 0 if isinstance(pos, int) else "no"
        df[spec.target_column] = [pos if v == 1 else neg for v in y]
        if degrade:
            df = health_mod.degrade(df, spec.target_column)
    out = project_dir(row.id) / "serving"
    out.mkdir(exist_ok=True)
    p = out / ("sample_labeled.csv" if labeled else "sample_new_rows.csv")
    df.to_csv(p, index=False)
    return p


@app.post("/projects/{project_id}/lists", response_model=ListOut)
async def create_list(project_id: str, file: UploadFile | None = File(None), sample: bool = False, n: int = 2000, top_n: int | None = None,
                      s: Session = Depends(get_session)) -> ListOut:
    """Upload new rows (or `sample=true` for fresh holdout rows), score them with the active model, return the ranked list."""
    row = get_project(project_id, s)
    spec = row.spec()
    if not spec or not row.protect():
        raise HTTPException(409, "run protection first")
    version = _active_version(row, s)
    if file is not None:
        src = project_dir(project_id) / "lists" / "upload.csv"
        src.parent.mkdir(exist_ok=True)
        await _save_upload(file, src)
    elif sample:
        src = _sample_rows(row, n, labeled=False, degrade=False)
    else:
        raise HTTPException(400, "upload a CSV or pass sample=true")
    try:
        rec = lists_mod.build(s, row, version, spec, src, top_n=top_n)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return lists_mod.to_out(rec, row.template, spec)


@app.get("/projects/{project_id}/lists", response_model=list[ListOut])
def get_lists(project_id: str, s: Session = Depends(get_session)) -> list[ListOut]:
    row = get_project(project_id, s)
    recs = lists_mod.for_project(s, project_id)
    return [lists_mod.to_out(r, row.template, row.spec(), preview=(i == 0)) for i, r in enumerate(recs)]


@app.get("/projects/{project_id}/lists/{list_id}", response_model=ListOut)
def get_list(project_id: str, list_id: str, s: Session = Depends(get_session)) -> ListOut:
    row = get_project(project_id, s)
    rec = s.get(ListRow, list_id)
    if rec is None or rec.project_id != project_id:
        raise HTTPException(404, "no such list")
    return lists_mod.to_out(rec, row.template, row.spec())


@app.get("/projects/{project_id}/lists/{list_id}/download")
def download_list(project_id: str, list_id: str, s: Session = Depends(get_session)):
    get_project(project_id, s)
    rec = s.get(ListRow, list_id)
    if rec is None or rec.project_id != project_id or not Path(rec.path).exists():
        raise HTTPException(404, "no such list")
    slug = rec.name.lower().replace(" ", "-")
    return FileResponse(rec.path, media_type="text/csv", filename=f"{slug}-v{rec.model_version}-{rec.created_at:%Y%m%d}.csv")


@app.post("/projects/{project_id}/health", response_model=HealthOut)
async def check_health(project_id: str, file: UploadFile | None = File(None), sample: bool = False, degrade: bool = False, n: int = 2000,
                       s: Session = Depends(get_session)) -> HealthOut:
    """Score fresh labeled rows with the active model and compare with its holdout score. Sets project.health."""
    import pandas as pd  # noqa: PLC0415

    row = get_project(project_id, s)
    spec = row.spec()
    if not spec or not row.protect():
        raise HTTPException(409, "run protection first")
    version = _active_version(row, s)
    if file is not None:
        src = project_dir(project_id) / "serving" / "health_upload.csv"
        src.parent.mkdir(exist_ok=True)
        await _save_upload(file, src)
    elif sample:
        src = _sample_rows(row, n, labeled=True, degrade=degrade)
    else:
        raise HTTPException(400, "upload a labeled CSV or pass sample=true")
    try:
        result = health_mod.evaluate(project_id, version, spec, pd.read_csv(src, low_memory=False), drift_threshold=row.drift_threshold)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    row.health = result.health
    row.health_json = result.model_dump_json()
    row.updated_at = datetime.now(timezone.utc)
    s.add(row)
    s.commit()
    return result


@app.get("/projects/{project_id}/plan", response_model=PlanOut)
def improvement_plan(project_id: str, s: Session = Depends(get_session)) -> PlanOut:
    """Illustrative subscription plus success fee on the measured improvement over v1. No payment is taken."""
    return plan_mod.improvement_plan(s, get_project(project_id, s))


@app.get("/projects/{project_id}/sample-csv")
def sample_csv(project_id: str, n: int = 2000, labeled: bool = False, degrade: bool = False, s: Session = Depends(get_session)):
    """A fresh CSV for the demo: the newest holdout rows. `labeled=true` adds the outcome column (for the performance watch)."""
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    p = _sample_rows(row, n, labeled=labeled, degrade=degrade)
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
    resp = await _agent.turn(template=row.template, profile=prof, spec=row.spec(), history=row.intake(), user_message=body.message, prefer_cache=body.prefer_cache)
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
