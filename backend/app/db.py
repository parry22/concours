"""The database: Postgres in production (`CONCOURS_DATABASE_URL=postgresql+psycopg://...`), SQLite in workspace/ for
local development and tests.

`create_all` makes missing tables but never changes an existing one, so `migrate()` adds columns introduced after
a database was created, for either dialect, and maps legacy stage names onto the current ones.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH, WORKSPACE_DIR, env

WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = env("DATABASE_URL", f"sqlite:///{DB_PATH}")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
engine = (
    create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    if IS_SQLITE
    else create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
)


# Columns added after the first release, per table: name -> SQL type (with default where one is needed).
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "project": {
        "active_model_id": "VARCHAR",
        "min_improvement": "FLOAT DEFAULT 0.01",
        "drift_threshold": "FLOAT DEFAULT 0.10",
        "health": "VARCHAR DEFAULT 'unknown'",
        "health_json": "VARCHAR",
        "refresh_daily": "BOOLEAN DEFAULT FALSE",
        "updated_at": "TIMESTAMP",
        "fraud_settings_json": "VARCHAR",
        "mapping_json": "VARCHAR",
        "as_of": "VARCHAR",
        "data_end": "VARCHAR",
        "salt": "VARCHAR",
        "source": "VARCHAR DEFAULT 'sample'",
        "drift_json": "VARCHAR",
        "org_id": "VARCHAR",
    },
    "model_version": {"gates_json": "VARCHAR"},
    "submission": {"gates_json": "VARCHAR", "origin": "VARCHAR DEFAULT 'local'", "hotkey": "VARCHAR", "uid": "INTEGER",
                   "chain_block": "INTEGER", "code_sha": "VARCHAR", "code_path": "VARCHAR"},
    "chain_state": {"solvers": "INTEGER"},
}
_LEGACY_STAGES = {"arena": "improve", "serve": "improve"}


def init_db() -> None:
    import app.auth  # noqa: F401  (register tables)
    import app.chain  # noqa: F401
    import app.jobs  # noqa: F401
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    migrate()


def migrate() -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in _ADDED_COLUMNS.items():
            if not insp.has_table(table):
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in cols.items():
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        for old, new in _LEGACY_STAGES.items():
            conn.execute(text("UPDATE project SET stage = :new WHERE stage = :old"), {"new": new, "old": old})
        conn.execute(text("UPDATE project SET updated_at = created_at WHERE updated_at IS NULL"))


@contextmanager
def session() -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def get_session() -> Iterator[Session]:
    with Session(engine) as s:
        yield s
