"""Handoff zip: the competition folder minus the private holdout, plus HANDOFF.md, leakage report and checksums.

Repo zip: the whole competition folder, holdout included, to push to the PRIVATE competition repo. release.yml builds
the referee image in GitHub Actions and referee/Dockerfile copies referee/data/, so the holdout has to be in that repo.
"""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from app.arena.stage import HIDDEN_FILES, competition_dir
from app.config import project_dir
from app.packager.protect import sha256_file

EXCLUDE_DIRS = ("out", "__pycache__")
GITHUB_FILE_LIMIT_MB = 100  # GitHub rejects pushes with a larger file
PRIVATE_WARNING = """> **Keep this repository and its GHCR packages PRIVATE.**
> `referee/data/` holds the hidden leaderboard slice and the private holdout with their labels. The release workflow
> bakes them into the referee image, so the `-referee` package on GHCR carries them too. Making either public hands
> every solver the answers. Grant Macrocosmos read access to the repo and both packages instead.

"""


def _files(comp: Path) -> list[Path]:
    return [p for p in sorted(comp.rglob("*"))
            if p.is_file() and not any(part in EXCLUDE_DIRS for part in p.relative_to(comp).parts)]


def build_zip(project_id: str) -> Path:
    comp = competition_dir(project_id)
    out = project_dir(project_id) / "handoff.zip"
    hidden_paths = {comp / "referee" / "data" / f for f in HIDDEN_FILES}
    lines = ["# SHA-256 checksums", "", "Private holdout files are NOT in this package. Transferred separately over a secure channel.", ""]
    for p in sorted(hidden_paths):
        if p.exists():
            lines.append(f"{sha256_file(p)}  referee/data/{p.name}  (excluded)")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in _files(comp):
            if p in hidden_paths:
                continue
            z.write(p, str(p.relative_to(comp)))
            lines.append(f"{sha256_file(p)}  {p.relative_to(comp)}")
        z.writestr("CHECKSUMS.txt", "\n".join(lines) + "\n")
    return out


def build_repo_zip(project_id: str) -> Path:
    """The private competition repo's contents: everything in the competition folder, holdout included."""
    comp = competition_dir(project_id)
    out = project_dir(project_id) / "repo.zip"
    files = _files(comp)
    big = [f"{p.relative_to(comp)} ({p.stat().st_size / 1e6:.0f} MB)" for p in files if p.stat().st_size > GITHUB_FILE_LIMIT_MB * 1e6]
    if big:
        raise ValueError(f"GitHub rejects files over {GITHUB_FILE_LIMIT_MB} MB: {', '.join(big)}")
    lines = ["# SHA-256 checksums", "", "Includes the private holdout. This repository must stay private.", ""]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = str(p.relative_to(comp))
            if rel == "README.md":
                text = (PRIVATE_WARNING + p.read_text()).encode()
                z.writestr(rel, text)
                lines.append(f"{hashlib.sha256(text).hexdigest()}  {rel}")
                continue
            z.write(p, rel)
            lines.append(f"{sha256_file(p)}  {rel}")
        z.writestr("CHECKSUMS.txt", "\n".join(lines) + "\n")
    return out


def zip_contains_hidden(path: Path) -> bool:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    return any(f"referee/data/{f}" in names for f in HIDDEN_FILES)
