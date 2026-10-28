"""The worker process: `python -m app.worker`. Claims improvement rounds from the database and runs them in Docker,
one at a time. Run as many as the machine has room for (each round uses up to 2 CPUs and 2 GB for its solver)."""
from __future__ import annotations

import signal
import threading

from app.db import init_db
from app.jobs import work_forever
from app.observability import setup_logging


def main() -> None:
    setup_logging()
    init_db()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    work_forever(stop)


if __name__ == "__main__":
    main()
