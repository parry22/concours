"""Encryption at rest for the files that hold real identifiers: the pending upload, the canonical dataset, the ID map
and the recent payments. (Protected files given to solvers hold only scrambled IDs and stay plain.)

The key is `CONCOURS_DATA_KEY` (a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Without it, a key file is created at workspace/.data_key for local development, and production refuses to start
(`CONCOURS_ENV=production`). Losing the key makes those files unreadable; back it up with the database.
Files written before encryption existed (no header) are still read.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd
from cryptography.fernet import Fernet

from app.config import WORKSPACE_DIR, env

MAGIC = b"CONCOURS-ENC1\n"
_fernet: Fernet | None = None


def _key() -> bytes:
    k = env("DATA_KEY", "")
    if k:
        return k.encode()
    if env("ENV", "development") == "production":
        raise RuntimeError("CONCOURS_DATA_KEY is required in production")
    f = WORKSPACE_DIR / ".data_key"
    if not f.exists():
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        f.write_bytes(Fernet.generate_key())
        os.chmod(f, 0o600)
    return f.read_bytes().strip()


def fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_key())
    return _fernet


def write_bytes(path: Path, data: bytes) -> None:
    tmp = Path(str(path) + ".tmp")
    tmp.write_bytes(MAGIC + fernet().encrypt(data))
    tmp.replace(path)


def read_bytes(path: Path) -> bytes:
    raw = Path(path).read_bytes()
    if raw.startswith(MAGIC):
        return fernet().decrypt(raw[len(MAGIC):])
    return raw


def encrypt_in_place(path: Path) -> None:
    raw = Path(path).read_bytes()
    if not raw.startswith(MAGIC):
        write_bytes(path, raw)


def read_csv(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(read_bytes(path)), **kw)


def to_csv(df: pd.DataFrame, path: Path, **kw) -> None:
    buf = io.BytesIO()
    df.to_csv(buf, index=False, **kw)
    write_bytes(path, buf.getvalue())
