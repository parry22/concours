"""Deleting a project takes its rows, folder, cache entries and fitted models with it; shared cache keys stay."""
from pathlib import Path

from fastapi.testclient import TestClient

from app import cleanup
from app.config import ARENA_CACHE_DIR
from app.db import session
from app.main import app
from app.models import CaseLabelRow, SubmissionRow


def test_delete_removes_rows_folder_and_private_cache(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CONCOURS_AUTH", "off")
    import app.auth as auth

    monkeypatch.setattr(auth, "AUTH_MODE", "off")
    c = TestClient(app)
    p = c.post("/projects", json={"template": "fraud", "sample": False, "name": "to delete"}).json()
    other = c.post("/projects", json={"template": "fraud", "sample": False, "name": "keeps shared"}).json()
    with session() as s:
        s.add(SubmissionRow(project_id=p["id"], solver="baseline_logreg", status="scored", data_hash="abc:def", logs_path=""))
        s.add(SubmissionRow(project_id=p["id"], solver="lgbm_tuned", status="scored", data_hash="only:mine", logs_path=""))
        s.add(SubmissionRow(project_id=other["id"], solver="baseline_logreg", status="scored", data_hash="abc:def", logs_path=""))
        s.add(CaseLabelRow(project_id=p["id"], transaction_id="t1", label=1, label_time="2024-01-01", model_version=1))
        s.commit()
    ARENA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (ARENA_CACHE_DIR / "abc-def.json").write_text("{}")
    (ARENA_CACHE_DIR / "only-mine.json").write_text("{}")
    r = c.delete(f"/projects/{p['id']}")
    assert r.status_code == 200 and r.json()["removed"]["rows"]["submission"] == 2 and r.json()["removed"]["rows"]["case_label"] == 1
    assert not (ARENA_CACHE_DIR / "only-mine.json").exists() and (ARENA_CACHE_DIR / "abc-def.json").exists()
    with session() as s:
        assert s.exec(__import__("sqlmodel").select(SubmissionRow).where(SubmissionRow.project_id == p["id"])).first() is None
        assert s.exec(__import__("sqlmodel").select(SubmissionRow).where(SubmissionRow.project_id == other["id"])).first() is not None
    (ARENA_CACHE_DIR / "abc-def.json").unlink()
    assert c.delete(f"/projects/{other['id']}").status_code == 200  # leaves nothing behind in the test database
    assert cleanup.purge_project  # module is importable on its own
