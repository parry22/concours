"""Handoff zip: the competition folder minus the private holdout, plus HANDOFF.md, leakage report and checksums.

Repo zip: the whole competition folder, to push to the PRIVATE competition repo, with the holdout files encrypted.
release.yml decrypts them (HOLDOUT_KEY secret) in GitHub Actions before referee/Dockerfile copies referee/data/.
    python -m app.handoff.build key <project_id>   prints the key to store as that secret
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
> `referee/data/` holds the hidden leaderboard slice and, encrypted (`*.enc`), the private holdout with its labels.
> The release workflow decrypts the holdout with the `HOLDOUT_KEY` repository secret and bakes it into the referee
> image, so the `-referee` package on GHCR carries the answers in clear. Never make the package public; grant
> Macrocosmos read access to the two packages, not the repository.

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


def holdout_key(project_id: str) -> str:
    """The Fernet key the holdout is encrypted with in the repo export. Kept in private/holdout_key.txt, itself
    encrypted with the data key. The owner stores it as the competition repo's HOLDOUT_KEY Actions secret."""
    from cryptography.fernet import Fernet  # noqa: PLC0415

    from app import secure_store  # noqa: PLC0415

    f = project_dir(project_id) / "private" / "holdout_key.txt"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        secure_store.write_bytes(f, Fernet.generate_key())
    return secure_store.read_bytes(f).decode().strip()


def build_repo_zip(project_id: str) -> Path:
    """The private competition repo's contents: everything in the competition folder. The hidden holdout files are
    included encrypted (`<name>.enc`, Fernet, key from `holdout_key`); the release workflow decrypts them with the
    HOLDOUT_KEY secret before building the referee image, so the repo's history never holds the answers in clear."""
    from cryptography.fernet import Fernet  # noqa: PLC0415

    comp = competition_dir(project_id)
    out = project_dir(project_id) / "repo.zip"
    files = _files(comp)
    big = [f"{p.relative_to(comp)} ({p.stat().st_size / 1e6:.0f} MB)" for p in files if p.stat().st_size > GITHUB_FILE_LIMIT_MB * 1e6]
    if big:
        raise ValueError(f"GitHub rejects files over {GITHUB_FILE_LIMIT_MB} MB: {', '.join(big)}")
    hidden_paths = {comp / "referee" / "data" / f for f in HIDDEN_FILES}
    fernet = Fernet(holdout_key(project_id).encode())
    lines = ["# SHA-256 checksums", "", "The private holdout files are included ENCRYPTED (referee/data/*.enc, Fernet). The key is the",
             "repository's HOLDOUT_KEY Actions secret; the release workflow decrypts them before building the referee image.",
             "Plaintext checksums are listed so the decrypted files can be verified. This repository must stay private.", ""]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = str(p.relative_to(comp))
            if rel == "README.md":
                text = (PRIVATE_WARNING + p.read_text()).encode()
                z.writestr(rel, text)
                lines.append(f"{hashlib.sha256(text).hexdigest()}  {rel}")
                continue
            if p in hidden_paths:
                token = fernet.encrypt(p.read_bytes())
                z.writestr(rel + ".enc", token)
                lines.append(f"{hashlib.sha256(token).hexdigest()}  {rel}.enc")
                lines.append(f"{sha256_file(p)}  {rel}  (plaintext, decrypted by the release workflow)")
                continue
            if rel == ".gitignore":
                continue
            z.write(p, rel)
            lines.append(f"{sha256_file(p)}  {rel}")
        gi = (comp / ".gitignore").read_text() if (comp / ".gitignore").exists() else ""
        gi += "".join(f"referee/data/{f}\n" for f in HIDDEN_FILES)  # the plaintext never enters git
        z.writestr(".gitignore", gi)
        z.writestr("CHECKSUMS.txt", "\n".join(lines) + "\n")
    return out


def zip_contains_hidden(path: Path) -> bool:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    return any(f"referee/data/{f}" in names for f in HIDDEN_FILES)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "key":
        print(holdout_key(sys.argv[2]))
    else:
        sys.exit("usage: python -m app.handoff.build key <project_id>")
