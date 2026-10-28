"""Fraud setup over HTTP: only fraud is offered, a renamed-columns CSV maps, the three questions store settings."""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import config
from app.db import get_session
from app.main import app

from tests.test_fraud import synthetic


@pytest.fixture
def engine(tmp_path: Path, monkeypatch):
    from app import auth as _auth  # noqa: F401  (register tables; `import app.auth` would shadow the FastAPI app)
    from app import db
    from app import jobs as _jobs  # noqa: F401

    monkeypatch.setattr(config, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(_auth, "_attempts", {})  # sign-in throttling is per IP; every test client shares one
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    monkeypatch.setattr(db, "engine", eng)  # code that opens its own session (jobs, events) uses the test database too

    def session():
        with Session(eng) as s:
            yield s

    app.dependency_overrides[get_session] = session
    yield eng
    app.dependency_overrides.clear()


def signed_in(email: str = "lead@payco.test", org: str = "PayCo") -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/signup", json={"email": email, "password": "correct horse battery", "org_name": org})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def client(engine):
    return signed_in()


def test_only_fraud_is_offered(client):
    assert [t["id"] for t in client.get("/templates").json()] == ["fraud"]
    r = client.post("/projects", json={"template": "churn"})
    assert r.status_code == 400 and "not enabled" in r.text


def test_renamed_csv_maps_and_three_questions(client):
    raw = synthetic(days=40, per_day=100).rename(columns={
        "TRANSACTION_ID": "payment_id", "TX_DATETIME": "created_at", "TX_AMOUNT": "amount_usd",
        "CUSTOMER_ID": "user_id", "TX_FRAUD": "is_fraud", "TERMINAL_ID": "merchant_id",
    })
    p = client.post("/projects", json={"template": "fraud", "sample": False}).json()
    assert p["stage"] == "upload" and not p["schema_confirmed"]
    buf = io.BytesIO(raw.to_csv(index=False).encode())
    r = client.post(f"/projects/{p['id']}/data", files={"file": ("tx.csv", buf, "text/csv")})
    assert r.status_code == 200 and r.json()["n_rows"] == len(raw)

    sch = client.get(f"/projects/{p['id']}/schema").json()
    by = {f["name"]: f["column"] for f in sch["fields"]}
    assert by == {"transaction_id": "payment_id", "transaction_time": "created_at", "amount": "amount_usd", "customer_id": "user_id",
                  "is_fraud": "is_fraud", "merchant_or_terminal_id": "merchant_id", "currency": None, "label_time": None}
    assert sch["problems"] == [] and not sch["confirmed"]

    bad = client.put(f"/projects/{p['id']}/schema", json={"mapping": {**by, "amount": None}})
    assert bad.status_code == 400 and "amount" in bad.text

    p = client.put(f"/projects/{p['id']}/schema", json={"mapping": by}).json()
    assert p["schema_confirmed"] and p["stage"] == "intake" and p["as_of"]
    assert p["spec"]["primary_metric"] == "fraud_amount_per_day" and p["spec"]["target_column"] == "is_fraud"

    for answer, done in (("we can review 150 a day", False), ("12 a review and a 20 fee", False), ("about 6 weeks", True)):
        r = client.post(f"/projects/{p['id']}/intake", json={"message": answer}).json()
        assert r["done"] is done
    p = client.get(f"/projects/{p['id']}").json()
    assert p["fraud_settings"] == {"daily_capacity": 150, "review_cost": 12.0, "fraud_fee": 20.0, "label_delay_days": 42}
    assert p["spec"]["metric_params"] == {"capacity": 150, "fee": 20.0, "review_cost": 12.0}
    assert p["stage"] == "protect"


# ---------- accounts ----------


def test_everything_needs_sign_in(engine):
    anon = TestClient(app)
    assert anon.get("/projects").status_code == 401
    assert anon.get("/healthz").status_code == 200
    assert anon.get("/auth/config").json()["first_run"] is True


def test_login_logout_and_wrong_password(engine):
    signed_in()
    c = TestClient(app)
    assert c.post("/auth/login", json={"email": "lead@payco.test", "password": "wrong password!"}).status_code == 401
    r = c.post("/auth/login", json={"email": "LEAD@payco.test", "password": "correct horse battery"})
    assert r.status_code == 200 and r.json()["org_name"] == "PayCo" and r.json()["role"] == "owner"
    assert c.get("/auth/me").status_code == 200
    c.post("/auth/logout")
    assert c.get("/projects").status_code == 401


def test_second_signup_needs_an_invite_and_orgs_are_isolated(engine):
    owner = signed_in()
    pid = owner.post("/projects", json={"template": "fraud", "sample": False}).json()["id"]
    stranger = TestClient(app)
    r = stranger.post("/auth/signup", json={"email": "x@other.test", "password": "another long pass"})
    assert r.status_code == 403  # SIGNUP=first: only the first account may sign up freely
    invite = owner.post("/auth/invites", json={"email": "analyst@payco.test"}).json()["token"]
    mate = TestClient(app)
    r = mate.post("/auth/signup", json={"email": "analyst@payco.test", "password": "analyst long pass", "invite": invite})
    assert r.status_code == 200 and r.json()["role"] == "member"
    assert [p["id"] for p in mate.get("/projects").json()] == [pid]  # same organisation
    assert mate.post("/auth/invites", json={}).status_code == 403  # members cannot invite
    reuse = TestClient(app).post("/auth/signup", json={"email": "analyst2@payco.test", "password": "analyst long pass", "invite": invite})
    assert reuse.status_code == 400  # an invite works once


def test_other_org_cannot_see_or_touch_projects(engine, monkeypatch):
    from app import auth

    owner = signed_in()
    pid = owner.post("/projects", json={"template": "fraud", "sample": False}).json()["id"]
    monkeypatch.setattr(auth, "SIGNUP", "open")
    other = signed_in("risk@rival.test", "Rival")
    assert other.get("/projects").json() == []
    assert other.get(f"/projects/{pid}").status_code == 404
    assert other.delete(f"/projects/{pid}").status_code == 404
    assert owner.get(f"/projects/{pid}").status_code == 200


def test_api_key_for_the_cli(engine):
    owner = signed_in()
    key = owner.post("/auth/keys", json={"name": "laptop"}).json()
    assert key["token"].startswith("ck_") and key["prefix"] == key["token"][:10]
    cli = TestClient(app)
    h = {"Authorization": f"Bearer {key['token']}"}
    assert cli.get("/auth/me", headers=h).json()["email"] == "lead@payco.test"
    assert cli.post("/projects", json={"template": "fraud", "sample": False}, headers=h).status_code == 200
    assert [k["id"] for k in owner.get("/auth/keys").json()] == [key["id"]]
    owner.delete(f"/auth/keys/{key['id']}")
    assert cli.get("/projects", headers=h).status_code == 401


def test_sign_in_is_throttled(engine):
    signed_in()
    c = TestClient(app)
    codes = [c.post("/auth/login", json={"email": "lead@payco.test", "password": "nope nope nope"}).status_code for _ in range(12)]
    assert codes[:9] == [401] * 9 and codes[-1] == 429
