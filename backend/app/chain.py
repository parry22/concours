"""Bittensor: miners' attempts in, the subnet's state and the winner out.

Concours is the validator of its own subnet. The validator process (`subnet/concours_subnet/validator.py`, its own
venv with the bittensor SDK) reads miners' on-chain commitments, checks each one against the code the miner uploaded,
and forwards it here with an API key. Each attempt is scored like any other: the solver runs in the player container
against the referee on the private holdout, and it becomes a version only if it passes the five gates. The
validator then reads the winner back and sets weights on chain. This module holds no keys and talks to no chain.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Field as SQLField
from sqlmodel import Session, SQLModel, select

from app.config import project_dir
from app.db import get_session
from app.models import ProjectRow, SubmissionRow

MAX_CODE_BYTES = 200_000
SS58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{47,48}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChainStateRow(SQLModel, table=True):
    """What the validator last reported for a project's subnet."""

    __tablename__ = "chain_state"

    project_id: str = SQLField(primary_key=True)
    network: str = "test"
    netuid: int = 0
    validator_hotkey: str = ""
    block: int | None = None
    solvers: int | None = None  # registered uids other than the validator
    weights_json: str | None = None  # {uid: weight} last set on chain
    weights_block: int | None = None
    note: str | None = None
    updated_at: datetime = SQLField(default_factory=_now)


class ChainSubmissionIn(BaseModel):
    hotkey: str
    uid: int
    block: int  # the block the miner's commitment was published at
    sha256: str
    code: str
    network: str = "test"
    netuid: int


class ChainStateIn(BaseModel):
    network: str
    netuid: int
    validator_hotkey: str
    block: int | None = None
    solvers: int | None = None  # registered uids other than the validator
    weights: dict[int, float] | None = None
    weights_block: int | None = None
    note: str | None = None


class MinerOut(BaseModel):
    submission_id: str
    hotkey: str
    uid: int | None
    block: int | None
    code_sha: str
    status: str
    private_score: float | None = None
    gates_passed: int | None = None
    error: str | None = None
    active: bool = False


class ChainOut(BaseModel):
    network: str | None = None
    netuid: int | None = None
    validator_hotkey: str | None = None
    block: int | None = None
    solvers: int | None = None  # registered uids other than the validator
    weights: dict[int, float] = Field(default_factory=dict)
    weights_block: int | None = None
    note: str | None = None
    updated_at: datetime | None = None
    winner_hotkey: str | None = None  # the miner whose code is the active version, if any
    winner_uid: int | None = None
    attempts: list[MinerOut] = Field(default_factory=list)


router = APIRouter(prefix="/projects/{project_id}/chain", tags=["bittensor"])


def _project(project_id: str, s: Session) -> ProjectRow:
    from app.main import _fraud_row  # noqa: PLC0415  (org check lives there)

    return _fraud_row(project_id, s)


def chain_out(s: Session, project_id: str) -> ChainOut:
    from app.models_registry import promotion  # noqa: PLC0415

    st = s.get(ChainStateRow, project_id)
    active = promotion.active_version(s, project_id)
    active_sub = s.get(SubmissionRow, active.submission_id) if active and active.submission_id else None
    winner = active_sub if active_sub is not None and active_sub.origin == "chain" else None
    subs = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.origin == "chain")
                  .order_by(SubmissionRow.created_at.desc())).all()
    attempts = []
    for r in subs:
        gates = json.loads(r.gates_json) if r.gates_json else None
        attempts.append(MinerOut(submission_id=r.id, hotkey=r.hotkey or "", uid=r.uid, block=r.chain_block, code_sha=r.code_sha or "",
                                 status=r.status, private_score=r.private_score, error=r.error,
                                 gates_passed=sum(1 for g in gates if g.get("passed")) if gates else None,
                                 active=winner is not None and r.code_sha == winner.code_sha))
    out = ChainOut(attempts=attempts, winner_hotkey=winner.hotkey if winner else None, winner_uid=winner.uid if winner else None)
    if st:
        out.network, out.netuid, out.validator_hotkey, out.block, out.solvers = st.network, st.netuid, st.validator_hotkey, st.block, st.solvers
        out.weights = {int(k): v for k, v in json.loads(st.weights_json or "{}").items()}
        out.weights_block, out.note, out.updated_at = st.weights_block, st.note, st.updated_at
    return out


@router.get("", response_model=ChainOut)
def get_chain(project_id: str, s: Session = Depends(get_session)) -> ChainOut:
    _project(project_id, s)
    return chain_out(s, project_id)


@router.put("/state", response_model=ChainOut)
def put_state(project_id: str, body: ChainStateIn, s: Session = Depends(get_session)) -> ChainOut:
    """The validator's heartbeat: network, netuid, current block, miner count and the weights it last set."""
    _project(project_id, s)
    st = s.get(ChainStateRow, project_id) or ChainStateRow(project_id=project_id)
    st.network, st.netuid, st.validator_hotkey = body.network, body.netuid, body.validator_hotkey
    st.block, st.solvers, st.note = body.block, body.solvers, body.note
    if body.weights is not None:
        st.weights_json = json.dumps({str(k): v for k, v in body.weights.items()})
        st.weights_block = body.weights_block
    st.updated_at = _now()
    s.add(st)
    s.commit()
    return chain_out(s, project_id)


@router.post("/submissions", response_model=MinerOut, status_code=202)
def post_submission(project_id: str, body: ChainSubmissionIn, s: Session = Depends(get_session)) -> MinerOut:
    """One miner's committed code. Starts an improvement round for it; 409 while another round runs."""
    from app.arena import service as arena  # noqa: PLC0415
    from app.models_registry import promotion  # noqa: PLC0415

    _project(project_id, s)
    if promotion.active_version(s, project_id) is None:
        raise HTTPException(409, "your first model is not ready yet")
    if not SS58.match(body.hotkey):
        raise HTTPException(400, "hotkey is not an ss58 address")
    code = body.code.encode()
    if len(code) > MAX_CODE_BYTES:
        raise HTTPException(413, f"submission is over {MAX_CODE_BYTES // 1000} KB")
    sha = hashlib.sha256(code).hexdigest()
    if sha != body.sha256.lower().removeprefix("0x"):
        raise HTTPException(400, "sha256 does not match the code")
    seen = s.exec(select(SubmissionRow).where(SubmissionRow.project_id == project_id, SubmissionRow.origin == "chain",
                                              SubmissionRow.code_sha == sha)).first()
    if seen is not None:
        return MinerOut(submission_id=seen.id, hotkey=seen.hotkey or "", uid=seen.uid, block=seen.chain_block, code_sha=sha,
                        status=seen.status, private_score=seen.private_score, error=seen.error)
    if arena.is_running(project_id):
        raise HTTPException(409, "a round is running; try again after it finishes")
    row = _project(project_id, s)
    from app.fraud import service as fraud  # noqa: PLC0415
    from app.main import _fraud_protect  # noqa: PLC0415

    if fraud.window_moved(row):
        _fraud_protect(row, s, keep_versions=True)  # the clock moved: score on the newest mature window, like a local round
    folder = project_dir(project_id) / "chain"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sha}.py"
    path.write_bytes(code)
    from app.arena.stage import data_hash  # noqa: PLC0415

    sub = SubmissionRow(project_id=project_id, solver=f"miner-{body.hotkey[:8]}-{sha[:8]}", status="queued",
                        data_hash=f"{data_hash(project_id)}:{sha[:16]}", logs_path="", origin="chain", hotkey=body.hotkey,
                        uid=body.uid, chain_block=body.block, code_sha=sha, code_path=str(path))
    s.add(sub)
    s.commit()
    s.refresh(sub)
    try:
        arena.start_chain_run(project_id, [sub.id])
    except RuntimeError as e:
        s.delete(sub)
        s.commit()
        raise HTTPException(409, str(e)) from e
    return MinerOut(submission_id=sub.id, hotkey=body.hotkey, uid=body.uid, block=body.block, code_sha=sha, status="queued")
