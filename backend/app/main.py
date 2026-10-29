"""Concours backend. One FastAPI app, SQLite + workspace/ on disk.

Flow: upload, intake, protect (which builds model version 1), model (lists, performance watch), improve
(contest rounds and promotions), launch (Apex handoff)."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.config import ALLOWED_ORIGINS, BASELINE_SOLVERS, ENABLED_TEMPLATES, MAX_UPLOAD_MB, TEMPLATES_DIR, project_dir
from app.db import get_session, init_db
from app.models import (
    ClockIn,
    DriftOut,
    FairnessReport,
    FraudSettings,
    QueueLabelIn,
    QueueOut,
    SchemaIn,
    SchemaOut,
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
from app import secure_store
from app.fraud import intake as fraud_intake
from app.fraud import service as fraud
from app.fraud.schema import profile as fraud_profile
from app.fraud.schema import schema_out
from app.packager import fairness
from app.packager.protect import protect
from app.templates import dataset_path, list_templates, load_defaults, spec_from_defaults

from app import auth  # noqa: E402
from app.observability import install as install_observability  # noqa: E402

app = FastAPI(title="Concours", version="0.3.0", description="Fraud models that keep up with fraudsters.",
              dependencies=[Depends(auth.require_auth)])
# Same-origin in production (Caddy serves the app and /api); a dev frontend on another port is listed explicitly.
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
install_observability(app)

STAGES = ["upload", "intake", "protect", "model", "improve", "launch"]


@app.on_event("startup")
def _startup() -> None:
    production_checks()
    init_db()


def production_checks() -> None:
    """`CONCOURS_ENV=production` refuses settings that are only safe on a laptop."""
    from app.config import env as _env  # noqa: PLC0415
    from app.db import IS_SQLITE  # noqa: PLC0415

    if _env("ENV", "development") != "production":
        return
    problems = []
    if IS_SQLITE:
        problems.append("CONCOURS_DATABASE_URL must point at Postgres")
    if not _env("DATA_KEY", ""):
        problems.append("CONCOURS_DATA_KEY is required (encryption at rest)")
    if auth.AUTH_MODE != "required":
        problems.append("CONCOURS_AUTH must be required")
    if not auth.COOKIE_SECURE:
        problems.append("CONCOURS_COOKIE_SECURE must be 1 (HTTPS only)")
    if auth.SIGNUP == "open":
        problems.append("CONCOURS_SIGNUP=open lets anyone create an organisation; use first or invite")
    if problems:
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))


def get_project(project_id: str, s: Session) -> ProjectRow:
    """A project of the caller's organisation; another organisation's project is reported as missing."""
    row = s.get(ProjectRow, project_id)
    org = auth.current_org.get()
    if not row or (org is not None and row.org_id != org):
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
    """Only the enabled templates (`CONCOURS_ENABLED_TEMPLATES`, default fraud). The rest stay in the code."""
    return [t for t in list_templates() if t["id"] in ENABLED_TEMPLATES]


@app.get("/projects", response_model=list[ProjectOut])
def list_projects(s: Session = Depends(get_session)) -> list[ProjectOut]:
    q = select(ProjectRow).order_by(ProjectRow.created_at.desc())
    if (org := auth.current_org.get()) is not None:
        q = q.where(ProjectRow.org_id == org)
    return [project_out(r, s) for r in s.exec(q).all()]


@app.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, s: Session = Depends(get_session)) -> ProjectOut:
    if body.template not in ENABLED_TEMPLATES:
        raise HTTPException(400, f"template {body.template} is not enabled")
    if body.template == "fraud":
        return _create_fraud(body, s)
    cfg = load_defaults(body.template) if body.template != "custom" else None
    row = ProjectRow(name=body.name or (cfg["name"] if cfg else "New problem"), template=body.template, org_id=auth.current_org.get())
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
    from app.cleanup import purge_project  # noqa: PLC0415

    row = get_project(project_id, s)
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the running round to finish")
    done = purge_project(s, project_id)
    s.delete(row)
    s.commit()
    return {"ok": True, "removed": done}


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
    dst = fraud.raw_path(project_id) if row.template == "fraud" else project_dir(project_id) / "dataset.csv"
    size = 0
    with open(dst, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB << 20:
                raise HTTPException(413, f"CSV larger than {MAX_UPLOAD_MB} MB")
            f.write(chunk)
    if row.template == "fraud":
        try:
            secure_store.encrypt_in_place(dst)
            prof = _profile_raw(row)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Could not read CSV: {e}") from e
        row.source = "upload"
        s.add(row)
        s.commit()
        return prof
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
    if row.template == "fraud":
        if not row.mapping_json:
            raise HTTPException(409, "map your columns first")
        report = _fraud_protect(row, s, keep_versions=False)
        try:
            arena.start_run(project_id, list(BASELINE_SOLVERS), replay=True, purpose="baseline")
        except RuntimeError:
            pass
        return report
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


@app.get("/projects/{project_id}/fairness", response_model=FairnessReport | None)
def fairness_report(project_id: str, s: Session = Depends(get_session)) -> FairnessReport | None:
    """Hit rate and selection rate per group of each sensitive column, for the active version on the holdout.
    Null before version 1 exists or when Protect set nothing aside."""
    return fairness.for_project(s, get_project(project_id, s))


# ---------- fraud ----------


def _create_fraud(body: ProjectCreate, s: Session) -> ProjectOut:
    """A fraud project: from the sample transactions (mapping screen next) or empty (the user uploads theirs)."""
    row = ProjectRow(name=body.name or ("Sample transactions" if body.sample else "My transactions"), template="fraud",
                     source="sample" if body.sample else "upload", salt=secure_store.encrypt_text(body.salt) if body.salt else None,
                     org_id=auth.current_org.get(), protect_version=body.protect_version or 2,
                     fraud_settings_json=FraudSettings().model_dump_json())
    s.add(row)
    s.commit()
    s.refresh(row)
    if body.sample:
        name = body.sample_file or load_defaults("fraud")["transactions"]
        src = TEMPLATES_DIR / "fraud" / Path(name).name
        if not src.exists():
            raise HTTPException(409, "the sample transactions are not fetched yet: run scripts/fetch_data.py fraud")
        shutil.copyfile(src, fraud.raw_path(row.id))
        secure_store.encrypt_in_place(fraud.raw_path(row.id))
        _profile_raw(row)
    s.add(row)
    s.commit()
    return project_out(row, s)


def _profile_raw(row: ProjectRow) -> DataProfile:
    import pandas as pd  # noqa: PLC0415
    from app.fraud.schema import suggest  # noqa: PLC0415

    df = secure_store.read_csv(fraud.raw_path(row.id), low_memory=False)
    sug = suggest(df)
    prof = fraud_profile(df, target=sug.get("is_fraud"), positive=1 if sug.get("is_fraud") else None)
    row.profile_json = prof.model_dump_json()
    row.mapping_json = None
    row.protect_json = None
    row.stage = "upload"
    row.updated_at = datetime.now(timezone.utc)
    return prof


def _fraud_row(project_id: str, s: Session) -> ProjectRow:
    row = get_project(project_id, s)
    if row.template != "fraud":
        raise HTTPException(400, "this endpoint is for fraud projects")
    return row


@app.get("/projects/{project_id}/schema", response_model=SchemaOut)
def get_schema(project_id: str, s: Session = Depends(get_session)) -> SchemaOut:
    """The mapping screen: the user's columns, the suggested mapping, a preview and what is still missing."""
    import json as _json  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    row = _fraud_row(project_id, s)
    cols_file = fraud.private_dir(project_id) / "columns.json"
    if not fraud.raw_path(project_id).exists():
        if row.mapping_json and cols_file.exists():  # confirmed: the upload is gone, the mapping and column names stay
            cols = _json.loads(cols_file.read_text())["columns"]
            return schema_out(pd.DataFrame(columns=cols), _json.loads(row.mapping_json), True)
        raise HTTPException(409, "upload your transactions first")
    df = secure_store.read_csv(fraud.raw_path(project_id), nrows=5000, low_memory=False)
    mapping = _json.loads(row.mapping_json) if row.mapping_json else None
    return schema_out(df, mapping, row.mapping_json is not None)


@app.put("/projects/{project_id}/schema", response_model=ProjectOut)
def put_schema(project_id: str, body: SchemaIn, s: Session = Depends(get_session)) -> ProjectOut:
    import pandas as pd  # noqa: PLC0415
    from app.fraud.schema import validate  # noqa: PLC0415

    row = _fraud_row(project_id, s)
    if not fraud.raw_path(project_id).exists():
        raise HTTPException(409, "upload your transactions first")
    problems = validate(secure_store.read_csv(fraud.raw_path(project_id), nrows=20000, low_memory=False), body.mapping)
    if problems:
        raise HTTPException(400, " ".join(problems))
    try:
        df = fraud.confirm_schema(row, body.mapping, sample=row.source == "sample")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    prof = fraud_profile(df.drop(columns=["label_time"]), target="is_fraud", positive=1)
    row.profile_json = prof.model_dump_json()
    row.protect_json = None
    advance(row, "intake")
    s.add(row)
    s.commit()
    return project_out(row, s)


@app.put("/projects/{project_id}/fraud-settings", response_model=ProjectOut)
def put_fraud_settings(project_id: str, body: FraudSettings, s: Session = Depends(get_session)) -> ProjectOut:
    row = _fraud_row(project_id, s)
    row.fraud_settings_json = body.model_dump_json()
    row.set_spec(fraud.spec_for(body))
    if row.mapping_json:
        advance(row, "protect")
    s.add(row)
    s.commit()
    return project_out(row, s)


def _fraud_protect(row: ProjectRow, s: Session, *, keep_versions: bool) -> ProtectReport:
    try:
        report = fraud.run_protect(s, row)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not keep_versions:
        for v in promotion.versions_for(s, row.id):
            s.delete(v)
        row.active_model_id = None
        row.finalized = False
        row.health, row.health_json, row.drift_json = "unknown", None, None
        row.stage = "protect"
    row.updated_at = datetime.now(timezone.utc)
    s.add(row)
    s.commit()
    return report


def _start_fraud_round(project_id: str, solvers: list[str] | None = None) -> list[str]:
    return arena.start_run(project_id, solvers or list(runner.FRAUD_CONTEST), replay=True, purpose="contest")


@app.get("/projects/{project_id}/queue", response_model=QueueOut)
def get_queue(project_id: str, s: Session = Depends(get_session)) -> QueueOut:
    """Today's review queue: today's payments ranked by expected loss, cut at the daily capacity, with reasons."""
    row = _fraud_row(project_id, s)
    v = promotion.active_version(s, project_id)
    if v is None:
        raise HTTPException(409, "your first model is not ready yet")
    if fraud.window_moved(row):
        raise HTTPException(409, "the data moved forward; run the improvement round to refresh the model first")
    return fraud.build_queue(s, row, v)


@app.post("/projects/{project_id}/queue/{transaction_id}/label", response_model=QueueOut)
def label_case(project_id: str, transaction_id: str, body: QueueLabelIn, s: Session = Depends(get_session)) -> QueueOut:
    """An analyst's verdict. Stored with label_time = today; used by the next improvement round."""
    row = _fraud_row(project_id, s)
    v = promotion.active_version(s, project_id)
    if v is None:
        raise HTTPException(409, "your first model is not ready yet")
    fraud.set_label(s, row, transaction_id, body.label, v.version)
    return fraud.build_queue(s, row, v)


@app.get("/projects/{project_id}/queue/download")
def queue_download(project_id: str, s: Session = Depends(get_session)):
    from fastapi.responses import Response  # noqa: PLC0415

    row = _fraud_row(project_id, s)
    v = promotion.active_version(s, project_id)
    if v is None:
        raise HTTPException(409, "your first model is not ready yet")
    q = fraud.build_queue(s, row, v)
    name = f"review-queue-{q.day}-v{q.model_version}.csv"
    return Response(fraud.queue_csv(q), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/projects/{project_id}/ratio")
def visa_ratio(project_id: str, s: Session = Depends(get_session)) -> dict:
    """Fraud-and-dispute ratio by month from the labels, against Visa's 1.5% monitoring threshold and count floor."""
    row = _fraud_row(project_id, s)
    if not row.mapping_json:
        raise HTTPException(409, "map your columns first")
    return fraud.monthly_ratio(row)


@app.get("/projects/{project_id}/drift", response_model=DriftOut | None)
def get_drift(project_id: str, s: Session = Depends(get_session)) -> DriftOut | None:
    """The last health and drift check (made when the clock moves or on POST)."""
    return _fraud_row(project_id, s).drift()


@app.post("/projects/{project_id}/drift", response_model=DriftOut)
def run_drift(project_id: str, s: Session = Depends(get_session)) -> DriftOut:
    row = _fraud_row(project_id, s)
    out = fraud.check(s, row)
    row.drift_json = out.model_dump_json()
    row.health = "slipping" if out.slipping else "healthy" if out.model_version else row.health
    s.add(row)
    s.commit()
    return out


@app.post("/projects/{project_id}/clock", response_model=DriftOut)
def move_clock(project_id: str, body: ClockIn, s: Session = Depends(get_session)) -> DriftOut:
    """Jump forward: move "today", check the newly mature weeks and drift. If the model is slipping and
    `auto_round`, the data window moves forward and an improvement round starts (the champion first)."""
    row = _fraud_row(project_id, s)
    if promotion.active_version(s, project_id) is None:
        raise HTTPException(409, "your first model is not ready yet")
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the running round to finish")
    if not (row.as_of and row.data_end and row.as_of < row.data_end):
        raise HTTPException(400, "This file has no payments after today, so there is nothing to move into. Upload newer transactions instead.")
    out, moved = fraud.jump(s, row, body.days)
    s.add(row)
    s.commit()
    if out.slipping and body.auto_round and moved:
        _fraud_protect(row, s, keep_versions=True)
        _start_fraud_round(project_id)
        advance(row, "improve")
        out.round_started = True
        row.drift_json = out.model_dump_json()
        s.add(row)
        s.commit()
    return out


# ---------- arena ----------

import asyncio  # noqa: E402

from sse_starlette.sse import EventSourceResponse  # noqa: E402

from app.arena import events, leaderboard, runner, service as arena  # noqa: E402
from app.models import LeaderboardOut, SubmissionRow  # noqa: E402


@app.on_event("startup")
def _worker_inline() -> None:
    from app import jobs as _jobs  # noqa: PLC0415

    if _jobs.WORKER_MODE == "inline":
        _jobs.ensure_inline_worker()


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
    if row.template == "fraud" and fraud.window_moved(row) and not arena.is_running(project_id):
        _fraud_protect(row, s, keep_versions=True)  # the clock moved: the round runs on the newest mature window
    solvers = body.solvers or (list(runner.FRAUD_CONTEST) if row.template == "fraud" else runner.SOLVERS)
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


import threading as _threading  # noqa: E402

from app.config import env as _cfg_env  # noqa: E402

# Live streams poll the database; a tab left open costs a query every half second, so each project allows a few
# streams, polling slows down when nothing happens, and a stream ends after a while (the page reconnects).
MAX_STREAMS_PER_PROJECT = int(_cfg_env("MAX_STREAMS", "10"))
STREAM_MAX_S = int(_cfg_env("STREAM_MAX_S", "1800"))
_streams: dict[str, int] = {}
_streams_lock = _threading.Lock()


def _take_stream(project_id: str) -> bool:
    with _streams_lock:
        if _streams.get(project_id, 0) >= MAX_STREAMS_PER_PROJECT:
            return False
        _streams[project_id] = _streams.get(project_id, 0) + 1
        return True


def _release_stream(project_id: str) -> None:
    with _streams_lock:
        _streams[project_id] = max(0, _streams.get(project_id, 0) - 1)


@app.get("/projects/{project_id}/arena/stream")
async def arena_stream(project_id: str, request: Request):
    """Live events (from the database, so the worker can be another process). Starts at the newest event."""
    import time as _time  # noqa: PLC0415

    from app import jobs as _jobs  # noqa: PLC0415
    from app.db import session as _session  # noqa: PLC0415

    def _own() -> None:
        with _session() as s:
            get_project(project_id, s)  # 404 for another organisation's project

    await asyncio.to_thread(_own)
    if not _take_stream(project_id):
        raise HTTPException(429, "Too many live views of this project are open. Close a tab and try again.")
    after = await asyncio.to_thread(_jobs.last_event_id, project_id)

    async def gen():
        nonlocal after
        started = _time.monotonic()
        try:
            yield {"event": "connected", "data": "{}"}
            idle = 0.0
            while not await request.is_disconnected() and _time.monotonic() - started < STREAM_MAX_S:
                rows = await asyncio.to_thread(_jobs.events_after, project_id, after)
                for r in rows:
                    after = r.id
                    yield {"event": r.event, "data": r.data}
                if rows:
                    idle = 0.0
                    continue
                wait = 0.5 if idle < 60 else 2.0  # a quiet stream polls less often
                await asyncio.sleep(wait)
                idle += wait
                if idle and int(idle) % 15 == 0:
                    yield {"event": "ping", "data": "{}"}
        finally:
            _release_stream(project_id)

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
from app.handoff.build import build_repo_zip, build_zip  # noqa: E402
from app.models import ListRow, PackageOut  # noqa: E402


@app.post("/projects/{project_id}/package", response_model=PackageOut)
def build_package(project_id: str, s: Session = Depends(get_session)) -> PackageOut:
    row = get_project(project_id, s)
    if not row.protect():
        raise HTTPException(409, "run protection first")
    if arena.is_running(project_id):
        raise HTTPException(409, "wait for the arena run to finish")
    from app.arena.stage import data_hash, stage  # noqa: PLC0415

    dh = data_hash(project_id)
    if not runner.images_current(project_id, dh):
        # cached replays never built this project's images, or the window moved since: build them now
        stage(project_id, row.spec())
        runner.build_images(project_id, lambda line: None, data=dh)
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


@app.get("/projects/{project_id}/package/repo")
def package_repo(project_id: str, s: Session = Depends(get_session)):
    """The PRIVATE competition repo's contents, holdout included (release.yml builds the referee image from it)."""
    row = get_project(project_id, s)
    if not row.package_json:
        raise HTTPException(409, "build the package first")
    try:
        path = build_repo_zip(project_id)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return FileResponse(path, media_type="application/zip", filename=f"concours-repo-{generator.competition_id(row)}.zip")


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
    if row.template == "fraud":
        return _fraud_intake(row, body, s)
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


def _fraud_intake(row: ProjectRow, body: IntakeRequest, s: Session) -> IntakeResponse:
    from app.models import SpecPatch  # noqa: PLC0415

    if not row.mapping_json:
        raise HTTPException(409, "map your columns first")
    hist, st, reply, done = fraud_intake.turn(row.intake(), body.message, fraud.settings_of(row))
    row.set_intake(hist)
    row.fraud_settings_json = st.model_dump_json()
    spec = fraud.spec_for(st)
    row.set_spec(spec)
    if done:
        advance(row, "protect")
    s.add(row)
    s.commit()
    return IntakeResponse(message=reply, spec_patch=SpecPatch(), spec=spec, done=done, source="defaults", history=hist)


@app.get("/intake/fraud-questions")
def fraud_questions() -> dict:
    return {"questions": fraud_intake.QUESTIONS, "suggested": fraud_intake.SUGGESTED}


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


from app import chain  # noqa: E402

app.include_router(chain.router)

from app.arena import apex_local  # noqa: E402

app.include_router(apex_local.router)


# ---------- trust page ----------


@app.get("/projects/{project_id}/trust")
def trust_facts(project_id: str, s: Session = Depends(get_session)) -> dict:
    """What leaves this machine, who can see what, and how the data is held: facts from the project, for the trust page."""
    from app.arena import apex_local as _apex  # noqa: PLC0415
    from app.config import env as _env  # noqa: PLC0415

    row = get_project(project_id, s)
    rep = row.protect()
    prof = row.profile()
    st = row.fraud_settings() if hasattr(row, "fraud_settings") else None
    return {
        "rows": prof.n_rows if prof else None,
        "columns_uploaded": prof.n_cols if prof else None,
        "kept_columns": rep.kept_columns if rep else [],
        "dropped_columns": rep.dropped_columns if rep else [],
        "hashed_columns": rep.hashed_columns if rep else [],
        "card_columns_dropped": [f.column for f in rep.findings if f.check == "pii" and f.action == "dropped"] if rep else [],
        "leak_columns_dropped": [f.column for f in rep.findings if f.check in ("target_leak", "future_info", "post_outcome_name") and f.action == "dropped"] if rep else [],
        "encrypted_at_rest": True,
        "encryption_key_location": "CONCOURS_DATA_KEY" if _env("DATA_KEY", "") else "workspace/.data_key on this machine",
        "raw_upload_deleted_after_mapping": True,
        "label_delay_days": st.label_delay_days if st else None,
        "holdout": {"rows": next((p.rows for p in rep.parts if p.name == "holdout"), None), "start": rep.maturity.holdout_start, "end": rep.maturity.holdout_end} if rep and rep.maturity else None,
        "train_rows": next((p.rows for p in rep.parts if p.name == "train"), None) if rep else None,
        "package_built": bool(row.package_json),
        "apex": _apex.status(),
        "analyst_labels": rep.maturity.analyst_labels if rep and rep.maturity else 0,
        "retention": "Everything stays until you delete the project; deleting removes the upload, the protected data, the queues and the labels.",
    }
