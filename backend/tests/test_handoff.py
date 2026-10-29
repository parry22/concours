"""Handoff zip excludes the private holdout and includes checksums + HANDOFF.md."""
import zipfile
from pathlib import Path

from app.arena.stage import HIDDEN_FILES
from app.handoff import build as hb


def test_zip_excludes_hidden(tmp_path: Path, monkeypatch):
    comp = tmp_path / "pid" / "competition"
    (comp / "referee" / "data").mkdir(parents=True)
    (comp / "player").mkdir()
    for f in ("leaderboard.csv", "leaderboard_labels.csv", *HIDDEN_FILES):
        (comp / "referee" / "data" / f).write_text("x\n1\n")
    (comp / "spec.yaml").write_text("schema: apex.competition.v1\n")
    (comp / "HANDOFF.md").write_text("# handoff\n")
    (comp / "player" / "submission.py").write_text("print(1)\n")
    (comp / "out").mkdir()
    (comp / "out" / "result.json").write_text("{}")
    monkeypatch.setattr(hb, "competition_dir", lambda pid: comp)
    monkeypatch.setattr(hb, "project_dir", lambda pid: tmp_path / "pid")
    z = hb.build_zip("pid")
    names = set(zipfile.ZipFile(z).namelist())
    assert not hb.zip_contains_hidden(z)
    assert "referee/data/leaderboard.csv" in names and "HANDOFF.md" in names and "CHECKSUMS.txt" in names
    assert "out/result.json" not in names
    txt = zipfile.ZipFile(z).read("CHECKSUMS.txt").decode()
    assert "holdout.csv  (excluded)" in txt and "secure channel" in txt


def _comp(tmp_path: Path, monkeypatch) -> Path:
    comp = tmp_path / "pid" / "competition"
    (comp / "referee" / "data").mkdir(parents=True)
    for f in ("leaderboard.csv", "leaderboard_labels.csv", *HIDDEN_FILES):
        (comp / "referee" / "data" / f).write_text("x\n1\n")
    (comp / "README.md").write_text("# Fraud competition\n")
    (comp / "spec.yaml").write_text("schema: apex.competition.v1\n")
    (comp / "out").mkdir()
    (comp / "out" / "result.json").write_text("{}")
    monkeypatch.setattr(hb, "competition_dir", lambda pid: comp)
    monkeypatch.setattr(hb, "project_dir", lambda pid: tmp_path / "pid")
    return comp


def test_repo_zip_includes_hidden_handoff_does_not(tmp_path: Path, monkeypatch):
    _comp(tmp_path, monkeypatch)
    repo = hb.build_repo_zip("pid")
    names = set(zipfile.ZipFile(repo).namelist())
    assert hb.zip_contains_hidden(repo)
    assert all(f"referee/data/{f}" in names for f in HIDDEN_FILES)
    assert "out/result.json" not in names
    readme = zipfile.ZipFile(repo).read("README.md").decode()
    assert readme.startswith("> **Keep this repository and its GHCR packages PRIVATE.**") and "# Fraud competition" in readme
    assert not hb.zip_contains_hidden(hb.build_zip("pid"))
    assert "# Fraud competition" == zipfile.ZipFile(hb.build_zip("pid")).read("README.md").decode().strip()


def test_repo_zip_refuses_files_github_rejects(tmp_path: Path, monkeypatch):
    comp = _comp(tmp_path, monkeypatch)
    monkeypatch.setattr(hb, "GITHUB_FILE_LIMIT_MB", 0.000001)
    import pytest
    with pytest.raises(ValueError, match="GitHub rejects"):
        hb.build_repo_zip("pid")
    assert comp.exists()
