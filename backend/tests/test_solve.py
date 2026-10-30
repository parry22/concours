"""Outside solvers with a solver key: keys from the owner, the kit, code in, the attempt's fate out."""
from __future__ import annotations

import io
import zipfile

import pytest
from sqlmodel import Session

from app import solve as solve_mod
from app.arena import service as arena
from app.models import ModelVersionRow, ProjectRow, SubmissionRow

from tests.test_fraud_api import engine, signed_in  # noqa: F401  (fixture)

CODE = "from common.base import SolverBase\n\nclass Solver(SolverBase):\n    name = 'outside'\n"


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


def test_owner_makes_a_key_and_the_solver_submits(setup, engine):
    c, pid, started = setup
    k = c.post(f"/projects/{pid}/solvers/keys", json={"name": "Ada"}).json()
    assert k["token"].startswith("sk_") and k["prefix"] == k["token"][:7] and k["attempts"] == 0
    listed = c.get(f"/projects/{pid}/solvers/keys").json()
    assert [x["name"] for x in listed] == ["Ada"] and listed[0]["token"] is None

    h = {"X-Solver-Key": k["token"]}
    me = c.get("/solve/me", headers=h).json()
    assert me["solver"] == "Ada" and me["active_version"] == 1 and me["active_per_day"] == 3714.0
    assert me["bar_per_day"] == pytest.approx(3714.0 * 1.01) and me["attempts"] == []

    r = c.post("/solve/submissions", json={"code": CODE}, headers=h)
    assert r.status_code == 202, r.text
    sub_id = r.json()["id"]
    assert started == [[sub_id]] and r.json()["status"] == "queued"
    with Session(engine) as s:
        sub = s.get(SubmissionRow, sub_id)
        assert sub.origin == "direct" and sub.submitted_by == "Ada" and sub.solver.startswith("solver-ada-")
        assert open(sub.code_path).read() == CODE and "/direct/" in sub.code_path
    again = c.post("/solve/submissions", json={"code": CODE}, headers=h)
    assert again.status_code == 202 and again.json()["id"] == sub_id and len(started) == 1
    assert c.get(f"/solve/submissions/{sub_id}", headers=h).json()["code_sha"] == sub.code_sha
    assert c.get(f"/projects/{pid}/solvers/keys").json()[0]["attempts"] == 1

    from app.arena.leaderboard import to_out  # noqa: PLC0415

    with Session(engine) as s:
        mine = to_out(s.get(SubmissionRow, sub_id), False)
    assert mine.origin == "direct" and mine.submitted_by == "Ada"


def test_bearer_header_works_too(setup):
    c, pid, _ = setup
    token = c.post(f"/projects/{pid}/solvers/keys", json={"name": "Bo"}).json()["token"]
    assert c.get("/solve/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_kit_holds_the_contract(setup):
    c, pid, _ = setup
    token = c.post(f"/projects/{pid}/solvers/keys", json={"name": "Ada"}).json()["token"]
    r = c.get("/solve/kit", headers={"X-Solver-Key": token})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "README.md" in names and "submission.py" in names and "common/base.py" in names
    readme = zipfile.ZipFile(io.BytesIO(r.content)).read("README.md").decode()
    assert "$3,714" in readme and "$3,751" in readme and "/solve/submissions" in readme


def test_bad_keys_and_bad_code_are_refused(setup):
    c, pid, started = setup
    assert c.get("/solve/me").status_code == 401
    assert c.get("/solve/me", headers={"X-Solver-Key": "sk_nope"}).status_code == 401
    k = c.post(f"/projects/{pid}/solvers/keys", json={"name": "Ada"}).json()
    h = {"X-Solver-Key": k["token"]}
    assert c.post("/solve/submissions", json={"code": "print('hi')"}, headers=h).status_code == 400
    big = "class Solver:\n" + "#" * (solve_mod.MAX_CODE_BYTES + 1)
    assert c.post("/solve/submissions", json={"code": big}, headers=h).status_code == 413
    assert started == []
    assert c.delete(f"/projects/{pid}/solvers/keys/{k['id']}").json() == {"ok": True}
    assert c.get("/solve/me", headers=h).status_code == 401
    assert c.get(f"/projects/{pid}/solvers/keys").json() == []
    assert c.post(f"/projects/{pid}/solvers/keys", json={"name": "   "}).status_code == 400


def test_promoted_attempt_is_credited(setup, engine):
    c, pid, _ = setup
    token = c.post(f"/projects/{pid}/solvers/keys", json={"name": "Ada"}).json()["token"]
    h = {"X-Solver-Key": token}
    sub_id = c.post("/solve/submissions", json={"code": CODE}, headers=h).json()["id"]
    with Session(engine) as s:  # the attempt passes the gates and becomes v2
        sub = s.get(SubmissionRow, sub_id)
        sub.status, sub.private_score = "scored", 6543.0
        s.add(sub)
        old = s.get(ModelVersionRow, s.get(ProjectRow, pid).active_model_id)
        old.status = "retired"
        v2 = ModelVersionRow(project_id=pid, version=2, status="active", source="outside", solver_name=sub.solver, submission_id=sub.id, private_score=6543.0)
        s.add_all([old, v2])
        s.commit()
        s.refresh(v2)
        row = s.get(ProjectRow, pid)
        row.active_model_id = v2.id
        s.add(row)
        s.commit()
    me = c.get("/solve/me", headers=h).json()
    assert me["active_version"] == 2 and me["attempts"][0]["active"] is True and me["attempts"][0]["version"] == 2
    assert me["attempts"][0]["business_value"] == "$6,543 of fraud caught per day"


def test_other_org_cannot_manage_keys(setup, monkeypatch):
    from app import auth  # noqa: PLC0415

    _, pid, _ = setup
    monkeypatch.setattr(auth, "SIGNUP", "open")
    other = signed_in("ops@other.test", "Other")
    assert other.get(f"/projects/{pid}/solvers/keys").status_code == 404
    assert other.post(f"/projects/{pid}/solvers/keys", json={"name": "x"}).status_code == 404


def test_source_for_origin():
    from app.models_registry.promotion import source_for

    assert source_for("direct") == "outside" and source_for("chain") == "bittensor" and source_for(None) == "local_contest"
