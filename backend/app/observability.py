"""Logs, request ids, health checks.

- One JSON line per request on stdout (method, path, status, ms, request id, organisation), so a log shipper
  or `docker compose logs` can be grepped. `CONCOURS_LOG_FORMAT=text` for plain lines in local dev.
- `X-Request-ID` is accepted from the proxy or generated, and echoed back.
- `/healthz`: the process is up. `/readyz`: the database answers and Docker (for improvement rounds) is reachable.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import env

LOG_FORMAT = env("LOG_FORMAT", "json")
log = logging.getLogger("concours")


class _Json(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname.lower(), "msg": record.getMessage(), "logger": record.name}
        for k in ("request_id", "method", "path", "status", "ms", "org"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def setup_logging() -> None:
    root = logging.getLogger()
    if any(getattr(h, "_concours", False) for h in root.handlers):
        return
    h = logging.StreamHandler(sys.stdout)
    h._concours = True  # type: ignore[attr-defined]
    h.setFormatter(_Json() if LOG_FORMAT == "json" else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(h)
    root.setLevel(env("LOG_LEVEL", "INFO").upper())


def install(app: FastAPI) -> None:
    setup_logging()

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"request_id": rid, "method": request.method, "path": request.url.path})
            response = JSONResponse({"detail": "Something went wrong on our side. The error is logged.", "request_id": rid}, status_code=500)
        response.headers["X-Request-ID"] = rid
        if request.url.path not in ("/healthz", "/readyz") and not request.url.path.endswith("/arena/status"):
            log.info("request", extra={"request_id": rid, "method": request.method, "path": request.url.path, "status": response.status_code,
                                       "ms": round((time.perf_counter() - t0) * 1000, 1), "org": getattr(request.state, "org", None)})
        return response

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict:
        return {"ok": True}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        from sqlalchemy import text  # noqa: PLC0415

        from app.arena import runner  # noqa: PLC0415
        from app.db import engine  # noqa: PLC0415

        checks = {}
        try:
            with engine.connect() as c:
                c.execute(text("select 1"))
            checks["database"] = "ok"
        except Exception as e:  # noqa: BLE001
            checks["database"] = f"error: {e}"[:200]
        ok, info = runner.docker_available()
        checks["docker"] = "ok" if ok else f"error: {info}"[:200]
        ready = all(v == "ok" for v in checks.values())
        return JSONResponse({"ready": ready, **checks}, status_code=200 if ready else 503)
