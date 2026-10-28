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
