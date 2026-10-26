"""Run with: uv run python -m app.workers.ingestion"""

import argparse
import logging
import signal
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.services.ingestion import process_next_job


def main() -> None:
    parser = argparse.ArgumentParser(description="Process RepoIQ's PostgreSQL ingestion queue")
    parser.add_argument("--once", action="store_true", help="Process at most one due batch and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Never log HTTP authorization, URLs with credentials, SQL parameters or source.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    settings = get_settings()
    stopping = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopping.set())
    logging.info("Ingestion worker started")
    failures = 0
    while not stopping.is_set():
        try:
            worked = process_next_job(settings)
            failures = 0
        except SQLAlchemyError:
            failures += 1
            logging.error("Database operation failed; batch rolled back")
            if args.once:
                raise SystemExit(1) from None
            stopping.wait(min(60, 2 ** min(failures, 6)))
            continue
        if args.once:
            break
        if not worked:
            stopping.wait(settings.ingestion_poll_seconds)
    logging.info("Ingestion worker stopped")


if __name__ == "__main__":
    main()
