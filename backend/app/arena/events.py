"""Live events for the UI stream. Stored in the database (app.jobs.EventRow) so a separate worker process can publish
them and every API process can stream them."""
from __future__ import annotations

from typing import Any

from app import jobs


def publish(project_id: str, event: str, data: Any) -> None:
    """Callable from any thread or process."""
    jobs.publish(project_id, event, data)
