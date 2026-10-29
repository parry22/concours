"""Bittensor intake over HTTP: a miner's committed code becomes an attempt, the winner and the subnet state read back."""
from __future__ import annotations

import hashlib

import pytest
from sqlmodel import Session

from app import chain as chain_mod
from app.arena import service as arena
from app.models import ModelVersionRow, ProjectRow, SubmissionRow

from tests.test_fraud_api import engine, signed_in  # noqa: F401  (fixture)

HOTKEY = "5GrxUU8dtnKQyfjr2msscQ8dhwjRcCb3CuewByAfxPdtV65d"
CODE = "from common.base import SolverBase\n\nclass Solver(SolverBase):\n    name = 'miner'\n"


@pytest.fixture
def setup(engine, monkeypatch):  # noqa: F811
    c = signed_in()
    pid = c.post("/projects", json={"template": "fraud", "sample": False}).json()["id"]
    with Session(engine) as s:
        row = s.get(ProjectRow, pid)
        v1 = ModelVersionRow(project_id=pid, version=1, status="active", source="baseline", solver_name="baseline_logreg", private_score=3714.0)
        s.add(v1)
        s.commit()
        row.active_model_id = v1.id
        s.add(row)
        s.commit()
    started: list[list[str]] = []
    monkeypatch.setattr(arena, "is_running", lambda project_id: False)
    monkeypatch.setattr(arena, "start_chain_run", lambda project_id, ids: started.append(ids) or ids)
    monkeypatch.setattr("app.arena.stage.data_hash", lambda project_id: "d" * 16)
    monkeypatch.setattr("app.fraud.service.window_moved", lambda row: False)
    return c, pid, started


def body(code: str = CODE, **kw) -> dict:
    return {"hotkey": HOTKEY, "uid": 2, "block": 2861, "sha256": hashlib.sha256(code.encode()).hexdigest(), "code": code, "netuid": 3, **kw}


def test_submission_starts_a_round_and_dedupes(setup, engine):
    c, pid, started = setup
    r = c.post(f"/projects/{pid}/chain/submissions", json=body())
    assert r.status_code == 202, r.text
    sub_id = r.json()["submission_id"]
    assert started == [[sub_id]]
    with Session(engine) as s:
        sub = s.get(SubmissionRow, sub_id)
        assert sub.origin == "chain" and sub.hotkey == HOTKEY and sub.uid == 2 and sub.chain_block == 2861
        assert sub.solver.startswith("miner-5GrxUU8d-") and open(sub.code_path).read() == CODE
    again = c.post(f"/projects/{pid}/chain/submissions", json=body())
    assert again.status_code == 202 and again.json()["submission_id"] == sub_id and len(started) == 1


def test_bad_submissions_are_refused(setup):
    c, pid, started = setup
    assert c.post(f"/projects/{pid}/chain/submissions", json=body(sha256="0" * 64)).status_code == 400
    assert c.post(f"/projects/{pid}/chain/submissions", json=body(hotkey="not-an-address")).status_code == 400
    big = "x" * (chain_mod.MAX_CODE_BYTES + 1)
    assert c.post(f"/projects/{pid}/chain/submissions", json=body(code=big)).status_code == 413
    assert started == []


def test_winner_and_state(setup, engine):
    c, pid, _ = setup
    sub_id = c.post(f"/projects/{pid}/chain/submissions", json=body()).json()["submission_id"]
    out = c.get(f"/projects/{pid}/chain").json()
    assert out["winner_hotkey"] is None and out["attempts"][0]["status"] == "queued"
    with Session(engine) as s:  # the miner's attempt passes the gates and becomes v2
        sub = s.get(SubmissionRow, sub_id)
        sub.status, sub.private_score = "scored", 6543.0
        s.add(sub)
        v1 = s.get(ProjectRow, pid).active_model_id
        old = s.get(ModelVersionRow, v1)
        old.status = "retired"
        v2 = ModelVersionRow(project_id=pid, version=2, status="active", source="bittensor", solver_name=sub.solver, submission_id=sub.id, private_score=6543.0)
        s.add_all([old, v2])
        s.commit()
    st = c.put(f"/projects/{pid}/chain/state", json={"network": "test", "netuid": 3, "validator_hotkey": HOTKEY, "block": 5210,
                                                      "solvers": 2, "weights": {"2": 1.0}, "weights_block": 5210}).json()
    assert st["winner_hotkey"] == HOTKEY and st["winner_uid"] == 2 and st["weights"] == {"2": 1.0} and st["solvers"] == 2
    assert st["attempts"][0]["active"] is True


def test_other_org_cannot_read_or_submit(setup, monkeypatch):
    from app import auth  # noqa: PLC0415

    _, pid, _ = setup
    monkeypatch.setattr(auth, "SIGNUP", "open")
    other = signed_in("ops@other.test", "Other")
    assert other.get(f"/projects/{pid}/chain").status_code == 404
    assert other.post(f"/projects/{pid}/chain/submissions", json=body()).status_code == 404
