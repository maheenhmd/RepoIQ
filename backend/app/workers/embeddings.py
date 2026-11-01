"""Run with uv run python -m app.workers.embeddings [--once]."""

import argparse
import logging
import signal
from threading import Event
from time import perf_counter

from app.core.config import get_settings
from app.db.embeddings import claim_batch, save_vectors, validate_dimension
from app.services.embeddings import EmbeddingService


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist local code embeddings")
    parser.add_argument("--once", action="store_true", help="Process at most one batch")
    parser.add_argument("--batch-size", type=int, choices=(4, 8, 16),
                        help="Override EMBEDDING_BATCH_SIZE for this run")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for name in ("httpx", "httpcore", "sentence_transformers", "transformers", "huggingface_hub"):
        logging.getLogger(name).setLevel(logging.ERROR)
    settings = get_settings()
    batch_size = args.batch_size or settings.embedding_batch_size
    service = EmbeddingService(settings)
    stopping = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopping.set())
    failures, total, ready = 0, 0, False
    while True:
        if stopping.is_set():
            break
        try:
            if not ready:
                # Downloads/model initialization and schema checks happen once,
                # before PostgreSQL row locks are acquired.
                service.load()
                validate_dimension(settings.embedding_dimension)
                ready = True
            started = perf_counter()
            with claim_batch(batch_size) as chunks:
                count = len(chunks)
                if count:
                    vectors = service.encode_code([
                        "\n".join(p for p in (c.context, c.content) if p) for c in chunks],
                        batch_size=batch_size)
                    save_vectors(chunks, vectors, service.identity)
            elapsed = perf_counter() - started
            total += count
            failures = 0
            rate = count / elapsed if elapsed else 0.0
            logging.info(
                "Embedding batch committed: chunks=%d seconds=%.2f chunks_per_second=%.2f total=%d",
                count, elapsed, rate, total)
        except Exception as exc:
            failures += 1
            # Exception text may contain SQL parameters/source. Log only its type.
            logging.error("Embedding batch failed (%s); progress rolled back; attempt %d/%d",
                          type(exc).__name__, failures, settings.embedding_max_attempts)
            if failures >= settings.embedding_max_attempts:
                raise SystemExit(1) from None
            stopping.wait(min(60, 5 * 2 ** (failures - 1)))
            continue
        if args.once or not count:
            break


if __name__ == "__main__":
    main()
