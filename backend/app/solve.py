"""Outside solvers without a chain: a solver key per person, a kit to download, code in, the attempt's fate out.

The owner creates a key for each outside solver on the Improve screen (`POST /projects/{id}/solvers/keys`). The solver
calls the `/solve/*` routes with that key (`X-Solver-Key: sk_...`): downloads the kit (the solver contract, the shared
feature code, the baseline to start from), submits one `submission.py`, and reads back how the attempt did. Every
submission is scored like any other attempt: in the player container, against the referee, on the private holdout,
through the five gates. One that passes becomes the next version, credited to the solver's name.

The Bittensor intake (`app/chain.py`) shares `intake_code`; only who vouches for the code differs (a key here, an
on-chain commitment there). The private holdout never leaves the server; a solver sees its own scores and gates only.
"""
from __future__ import annotations

import hashlib
import io
import re
import secrets
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, select

from app.config import SOLVERS_DIR, project_dir
from app.db import get_session
from app.models import ProjectRow, SubmissionRow

MAX_CODE_BYTES = 200_000
ORIGIN = "direct"
SOLVE_PREFIX = "/solve/"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return secrets.token_hex(6)


class SolverKeyRow(SQLModel, table=True):
    """One outside solver's key for one project. Only the SHA-256 of the token is stored."""

    __tablename__ = "solver_key"

    id: str = SQLField(default_factory=_id, primary_key=True)
    project_id: str = SQLField(index=True)
    name: str
    prefix: str = ""
    token_hash: str = SQLField(index=True, unique=True)
    created_at: datetime = SQLField(default_factory=_now)
    last_used_at: datetime | None = None
    revoked: bool = False


def new_token() -> str:
    return "sk_" + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---------- shared intake (also used by the Bittensor validator's route) ----------


def intake_code(s: Session, row: ProjectRow, code: bytes, *, origin: str, label: str, submitted_by: str | None = None,
                hotkey: str | None = None, uid: int | None = None, block: int | None = None) -> tuple[SubmissionRow, bool]:
    """Store one outside `submission.py` and start an improvement round for it. Returns (row, started).
    The same code from the same origin is returned, not duplicated. 409 while another round runs."""
    from app.arena import service as arena  # noqa: PLC0415
    from app.arena.stage import data_hash  # noqa: PLC0415
    from app.fraud import service as fraud  # noqa: PLC0415
    from app.main import _fraud_protect  # noqa: PLC0415
    from app.models_registry import promotion  # noqa: PLC0415

    project_id = row.id
    if promotion.active_version(s, project_id) is None:
        raise HTTPException(409, "your first model is not ready yet")
    if len(code) > MAX_CODE_BYTES:
        raise HTTPException(413, f"submission is over {MAX_CODE_BYTES // 1000} KB")
    if b"class Solver" not in code:
        raise HTTPException(400, "submission.py must define a class named Solver (see the kit's README)")
    sha = hashlib.sha256(code).hexdigest()
    seen = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.origin == origin,
                                              SubmissionRow.code_sha == sha)).first()
    if seen is not None:
        return seen, False
    if arena.is_running(project_id):
        raise HTTPException(409, "a round is running; try again after it finishes")
    if fraud.window_moved(row):
        _fraud_protect(row, s, keep_versions=True)  # the clock moved: score on the newest mature window, like a local round
    folder = project_dir(project_id) / origin
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}.py"
    path.write_bytes(code)
    sub = SubmissionRow(project_id=project_id, solver=label, status="queued", data_hash=f"{data_hash(project_id)}:{sha[:16]}",
                        logs_path="", origin=origin, submitted_by=submitted_by, hotkey=hotkey, uid=uid, chain_block=block,
                        code_sha=sha, code_path=str(path))
    s.add(sub)
    s.commit()
    s.refresh(sub)
    try:
        arena.start_chain_run(project_id, [sub.id])
    except RuntimeError as e:
        s.delete(sub)
        s.commit()
        raise HTTPException(409, str(e)) from e
    return sub, True


# ---------- owner side: keys ----------


class SolverKeyIn(BaseModel):
    name: str


class SolverKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    attempts: int = 0
    token: str | None = None  # only on creation


owner = APIRouter(prefix="/projects/{project_id}/solvers", tags=["solvers"])


def _project(project_id: str, s: Session) -> ProjectRow:
    from app.main import _fraud_row  # noqa: PLC0415  (organisation check lives there)

    return _fraud_row(project_id, s)


def _key_out(s: Session, k: SolverKeyRow, token: str | None = None) -> SolverKeyOut:
    n = len(s.exec(select(SubmissionRow.id).where(SubmissionRow.project_id == k.project_id, SubmissionRow.origin == ORIGIN,
                                                  SubmissionRow.submitted_by == k.name)).all())
    return SolverKeyOut(id=k.id, name=k.name, prefix=k.prefix, created_at=k.created_at, last_used_at=k.last_used_at, attempts=n, token=token)


@owner.get("/keys", response_model=list[SolverKeyOut])
def list_keys(project_id: str, s: Session = Depends(get_session)) -> list[SolverKeyOut]:
    _project(project_id, s)
    rows = s.exec(select(SolverKeyRow).where(SolverKeyRow.project_id == project_id, SolverKeyRow.revoked == False)  # noqa: E712
                  .order_by(SolverKeyRow.created_at)).all()
    return [_key_out(s, k) for k in rows]


@owner.post("/keys", response_model=SolverKeyOut, status_code=201)
def create_key(project_id: str, body: SolverKeyIn, s: Session = Depends(get_session)) -> SolverKeyOut:
    """A key for one outside solver, shown once."""
    _project(project_id, s)
    name = " ".join(body.name.split())[:60]
    if not name:
        raise HTTPException(400, "give the solver a name")
    token = new_token()
    k = SolverKeyRow(project_id=project_id, name=name, prefix=token[:7], token_hash=token_hash(token))
    s.add(k)
    s.commit()
    s.refresh(k)
    return _key_out(s, k, token)


@owner.delete("/keys/{key_id}")
def revoke_key(project_id: str, key_id: str, s: Session = Depends(get_session)) -> dict:
    _project(project_id, s)
    k = s.get(SolverKeyRow, key_id)
    if k is None or k.project_id != project_id:
        raise HTTPException(404, "no such key")
    k.revoked = True
    s.add(k)
    s.commit()
    return {"ok": True}


# ---------- solver side ----------


class Solver(BaseModel):
    key: SolverKeyRow
    project: ProjectRow

    model_config = {"arbitrary_types_allowed": True}


def solver(request: Request, s: Session = Depends(get_session), x_solver_key: str | None = Header(default=None)) -> Solver:
    token = x_solver_key or ""
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token.startswith("sk_"):
        raise HTTPException(401, "send your solver key in the X-Solver-Key header")
    k = s.exec(select(SolverKeyRow).where(SolverKeyRow.token_hash == token_hash(token))).first()
    if k is None or k.revoked:
        raise HTTPException(401, "this solver key is not valid")
    row = s.get(ProjectRow, k.project_id)
    if row is None:
        raise HTTPException(401, "this solver key is not valid")
    k.last_used_at = _now()
    s.add(k)
    s.commit()
    return Solver(key=k, project=row)


class AttemptOut(BaseModel):
    id: str
    status: str
    code_sha: str
    private_score: float | None = None
    business_value: str | None = None
    gates: list[dict] = []
    gates_passed: int | None = None
    error: str | None = None
    active: bool = False
    version: int | None = None
    created_at: datetime


class MeOut(BaseModel):
    project: str
    solver: str
    active_version: int | None = None
    active_per_day: float | None = None
    bar_per_day: float | None = None  # what an attempt must reach on the private holdout
    min_improvement: float
    daily_capacity: int | None = None
    round_running: bool = False
    attempts: list[AttemptOut] = []


class SubmitIn(BaseModel):
    code: str


public = APIRouter(prefix="/solve", tags=["solvers"])


def _attempts(s: Session, who: Solver) -> list[AttemptOut]:
    import json  # noqa: PLC0415

    from app.models_registry import promotion  # noqa: PLC0415

    pid = who.project.id
    by_sub = {v.submission_id: v for v in promotion.versions_for(s, pid) if v.submission_id}
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == pid, SubmissionRow.origin == ORIGIN,
                                              SubmissionRow.submitted_by == who.key.name).order_by(SubmissionRow.created_at.desc())).all()
    out = []
    for r in subs:
        gates = json.loads(r.gates_json) if r.gates_json else []
        v = by_sub.get(r.id)
        bv = f"${r.private_score:,.0f} of fraud caught per day" if r.status == "scored" and r.private_score is not None else None
        out.append(AttemptOut(id=r.id, status=r.status, code_sha=r.code_sha or "", private_score=r.private_score, business_value=bv,
                              gates=gates, gates_passed=sum(1 for g in gates if g.get("passed")) if gates else None, error=r.error,
                              active=v is not None and v.status == "active", version=v.version if v else None, created_at=r.created_at))
    return out


@public.get("/me", response_model=MeOut)
def me(who: Solver = Depends(solver), s: Session = Depends(get_session)) -> MeOut:
    """What the solver is up against: the active version's money per day, the bar, their own attempts."""
    from app.arena import service as arena  # noqa: PLC0415
    from app.models_registry import promotion  # noqa: PLC0415

    row = who.project
    active = promotion.active_version(s, row.id)
    fs = row.fraud_settings() if hasattr(row, "fraud_settings") else None
    cap = (fs or {}).get("daily_capacity") if isinstance(fs, dict) else getattr(fs, "daily_capacity", None)
    score = active.private_score if active else None
    return MeOut(project=row.name, solver=who.key.name, active_version=active.version if active else None, active_per_day=score,
                 bar_per_day=score * (1 + row.min_improvement) if score is not None else None, min_improvement=row.min_improvement,
                 daily_capacity=cap, round_running=arena.is_running(row.id), attempts=_attempts(s, who))


README = """# Concours solver kit: {project}

You are improving the fraud model for "{project}". Your attempt is measured the way every attempt is: it trains inside
a container on the training rows, then a referee scores it on recent days it never saw (the private holdout), with
labels as they were known then. The number that matters is fraud money caught per day inside a {capacity}-case review
queue. The active version catches {active} a day; a new version must reach {bar} a day and pass five gates
(hidden data only, same rows, a luck test over 1,000 day resamples, no segment regression over 5%, 10,000 rows scored
under 5 s).

## The contract

Submit one file, `submission.py`, under 200 KB, that defines `class Solver(SolverBase)` with:

- `fit(self, X: pd.DataFrame, y: np.ndarray) -> None`
- `predict_proba(self, X: pd.DataFrame) -> np.ndarray` (one score per row, higher = more likely fraud)

`common/base.py` (in this kit, present in the container at `/app/common/`) prepares the features the same way for
every solver and wraps your class; read it to see which columns you get. `submission.py` in this kit is the baseline:
start from it. The container has pandas, numpy, scikit-learn and lightgbm, no network, 2 CPUs, 2 GB of memory and
{timeout} s to train and score.

Customer and merchant IDs are hashed; card numbers are not present. You never see the holdout.

## Submit

    concours solve submit submission.py --key $CONCOURS_SOLVER_KEY --url {url}
    concours solve status --key $CONCOURS_SOLVER_KEY --url {url}

or, without the CLI:

    curl -X POST {url}/solve/submissions -H "X-Solver-Key: $CONCOURS_SOLVER_KEY" \\
         -H "Content-Type: application/json" --data @<(python -c 'import json,sys;print(json.dumps({{"code":open("submission.py").read()}}))')

One round runs at a time per project; a 409 means wait and resubmit. The same code is not scored twice.
"""


@public.get("/kit")
def kit(request: Request, who: Solver = Depends(solver), s: Session = Depends(get_session)) -> Response:
    """A zip: README, the baseline submission.py, the shared feature code."""
    from app.config import SOLVER_TIMEOUT_S  # noqa: PLC0415

    m = me(who, s)
    base = str(request.base_url).rstrip("/")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.md", README.format(project=m.project, capacity=m.daily_capacity or 200,
                                               active=f"${m.active_per_day:,.0f}" if m.active_per_day is not None else "n/a",
                                               bar=f"${m.bar_per_day:,.0f}" if m.bar_per_day is not None else "n/a",
                                               timeout=SOLVER_TIMEOUT_S, url=base))
        z.write(SOLVERS_DIR / "baseline_logreg" / "submission.py", "submission.py")
        for p in sorted((SOLVERS_DIR / "common").glob("*.py")):
            z.write(p, f"common/{p.name}")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="concours-solver-kit.zip"'})


@public.post("/submissions", response_model=AttemptOut, status_code=202)
def submit(body: SubmitIn, who: Solver = Depends(solver), s: Session = Depends(get_session)) -> AttemptOut:
    """One attempt. Starts an improvement round for it; the same code is returned, not re-scored."""
    code = body.code.encode()
    sha = hashlib.sha256(code).hexdigest()
    safe = re.sub(r"-+", "-", "".join(ch if ch.isalnum() else "-" for ch in who.key.name.lower()))[:16].strip("-") or "solver"
    sub, _ = intake_code(s, who.project, code, origin=ORIGIN, label=f"solver-{safe}-{sha[:8]}", submitted_by=who.key.name)
    return next(a for a in _attempts(s, who) if a.id == sub.id)


@public.get("/submissions/{sub_id}", response_model=AttemptOut)
def attempt(sub_id: str, who: Solver = Depends(solver), s: Session = Depends(get_session)) -> AttemptOut:
    for a in _attempts(s, who):
        if a.id == sub_id:
            return a
    raise HTTPException(404, "no such attempt")
