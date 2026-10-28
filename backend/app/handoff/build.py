"""Handoff zip: the competition folder minus the private holdout, plus HANDOFF.md, leakage report and checksums."""
from __future__ import annotations

import zipfile
from pathlib import Path

from app.arena.stage import HIDDEN_FILES, competition_dir
from app.config import project_dir
from app.packager.protect import sha256_file

EXCLUDE_DIRS = ("out", "__pycache__")


def build_zip(project_id: str) -> Path:
    comp = competition_dir(project_id)
    out = project_dir(project_id) / "handoff.zip"
    hidden_paths = {comp / "referee" / "data" / f for f in HIDDEN_FILES}
    lines = ["# SHA-256 checksums", "", "Private holdout files are NOT in this package. Transferred separately over a secure channel.", ""]
    for p in sorted(hidden_paths):
        if p.exists():
            lines.append(f"{sha256_file(p)}  referee/data/{p.name}  (excluded)")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(comp.rglob("*")):
            if not p.is_file() or p in hidden_paths or any(part in EXCLUDE_DIRS for part in p.relative_to(comp).parts):
                continue
            z.write(p, str(p.relative_to(comp)))
            lines.append(f"{sha256_file(p)}  {p.relative_to(comp)}")
        z.writestr("CHECKSUMS.txt", "\n".join(lines) + "\n")
    return out


def zip_contains_hidden(path: Path) -> bool:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    return any(f"referee/data/{f}" in names for f in HIDDEN_FILES)
