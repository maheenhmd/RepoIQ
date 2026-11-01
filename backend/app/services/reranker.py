"""Optional local ONNX cross-encoder. No network or framework imports on startup."""

import logging
from pathlib import Path
from threading import Lock

from app.core.config import get_vector_settings

logger = logging.getLogger(__name__)
_lock = Lock()
_session = None
_tokenizer = None
_failed = False


def _has_headroom(settings, *, loading: bool) -> bool:
    import psutil

    reserve = settings.reranker_headroom_mb * 1024**2
    limit = settings.reranker_memory_limit_mb * 1024**2
    used = psutil.Process().memory_info().rss
    # Account for all processes charged to a Linux container, not only this worker.
    for directory, limit_name, used_name in (
        ("/sys/fs/cgroup", "memory.max", "memory.current"),
        ("/sys/fs/cgroup/memory", "memory.limit_in_bytes", "memory.usage_in_bytes"),
    ):
        root = Path(directory)
        if (root / limit_name).exists():
            value = (root / limit_name).read_text().strip()
            if value != "max":
                limit = min(limit, int(value))
            used = max(used, int((root / used_name).read_text()))
            break
    needed = reserve if loading else max(64 * 1024**2, reserve // 3)
    return used + needed < limit and psutil.virtual_memory().available > needed


def rerank(query: str, candidates: list[dict]) -> list[dict] | None:
    """Return all candidates with raw logit ranking scores, or None for fallback.

    A nonblocking lock serializes loading/inference and bounds memory. Busy requests
    use fallback. A failed model is disabled until process restart.
    """
    global _session, _tokenizer, _failed
    settings = get_vector_settings()
    if not settings.reranker_enabled or _failed or not candidates:
        return None
    if len(candidates) > settings.reranker_top_n or not _lock.acquire(blocking=False):
        return None
    try:
        if not _has_headroom(settings, loading=_session is None):
            return None
        if _session is None:
            import onnxruntime as ort
            from tokenizers import Tokenizer

            root = Path(settings.reranker_path)
            tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=settings.reranker_max_length)
            tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.enable_cpu_mem_arena = False
            options.enable_mem_pattern = False
            options.log_severity_level = 4
            session = ort.InferenceSession(str(root / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
            if {item.name for item in session.get_inputs()} - {
                "input_ids", "attention_mask", "token_type_ids"
            }:
                raise ValueError("Unexpected model inputs")
            _session, _tokenizer = session, tokenizer
        import numpy as np

        scores = []
        for start in range(0, len(candidates), settings.reranker_batch_size):
            if not _has_headroom(settings, loading=False):
                return None
            batch = candidates[start:start + settings.reranker_batch_size]
            pairs = [(query[:2000], (
                f"{hit['file_path']} {hit['symbol_name']}\n{hit['content']}"
            )[:16000]) for hit in batch]
            encoded = _tokenizer.encode_batch(pairs)
            attributes = {"input_ids": "ids", "attention_mask": "attention_mask",
                          "token_type_ids": "type_ids"}
            inputs = {item.name: np.asarray([
                getattr(tokens, attributes[item.name]) for tokens in encoded
            ], dtype=np.int64) for item in _session.get_inputs()}
            logits = _session.run(None, inputs)[0]
            if logits.shape != (len(batch), 1) or not np.isfinite(logits).all():
                raise ValueError("Unexpected model output")
            scores.extend(float(value) for value in logits[:, 0])
        ranked = [dict(hit, ranking_score=score) for hit, score in zip(candidates, scores)]
        ranked.sort(key=lambda hit: (-hit['ranking_score'], -hit['similarity'], hit['chunk_id']))
        return ranked
    except Exception as exc:
        _failed = True
        _session = _tokenizer = None
        logger.warning("Reranker disabled; using fallback (%s)", type(exc).__name__)
        return None
    finally:
        _lock.release()
