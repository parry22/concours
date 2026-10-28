"""SQLite via SQLModel. One file in workspace/."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH, WORKSPACE_DIR

WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


# Columns added after the first release. `create_all` never alters an existing table, so an old workspace DB
# gets them here. Legacy stage names map onto the new six steps.
_PROJECT_COLUMNS = {
    "active_model_id": "VARCHAR",
    "min_improvement": "FLOAT DEFAULT 0.01",
    "drift_threshold": "FLOAT DEFAULT 0.10",
    "health": "VARCHAR DEFAULT 'unknown'",
    "health_json": "VARCHAR",
    "refresh_daily": "BOOLEAN DEFAULT 0",
    "updated_at": "DATETIME",
}
_LEGACY_STAGES = {"arena": "improve", "serve": "improve"}


def init_db() -> None:
    import app.models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    migrate()


def migrate() -> None:
    from sqlalchemy import text  # noqa: PLC0415

    with engine.begin() as conn:
        have = {r[1] for r in conn.exec_driver_sql("PRAGMA table_info(project)").fetchall()}
        for col, ddl in _PROJECT_COLUMNS.items():
            if col not in have:
                conn.exec_driver_sql(f"ALTER TABLE project ADD COLUMN {col} {ddl}")
        for old, new in _LEGACY_STAGES.items():
            conn.execute(text("UPDATE project SET stage = :new WHERE stage = :old"), {"new": new, "old": old})
        conn.exec_driver_sql("UPDATE project SET updated_at = created_at WHERE updated_at IS NULL")


@contextmanager
def session() -> Iterator[Session]:
    with Session(engine) as s:
        yield s


def get_session() -> Iterator[Session]:
    with Session(engine) as s:
        yield s
