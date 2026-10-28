"""In-process pub/sub for SSE. One queue per subscriber per project."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

_subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def publish(project_id: str, event: str, data: Any) -> None:
    """Thread-safe: callable from the worker thread."""
    payload = {"event": event, "data": json.dumps(data, default=str)}
    for q in list(_subs.get(project_id, ())):
        if _loop:
            _loop.call_soon_threadsafe(q.put_nowait, payload)
        else:
            q.put_nowait(payload)


def subscribe(project_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subs[project_id].add(q)
    return q


def unsubscribe(project_id: str, q: asyncio.Queue) -> None:
    _subs[project_id].discard(q)
