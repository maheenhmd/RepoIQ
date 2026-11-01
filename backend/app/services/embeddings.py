"""Local CodeRankEmbed inference; independent of database and worker lifecycle."""

import math

from app.core.config import VectorSettings


class EmbeddingService:
    QUERY_PREFIX = "Represent this query for searching relevant code: "

    def __init__(self, settings: VectorSettings):
        self.settings = settings
        self._model = None

    @property
    def identity(self) -> str:
        s = self.settings
        return f"{s.embedding_model}@{s.embedding_revision};tokens={s.embedding_max_tokens};code-v1"

    def load(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer

        s = self.settings
        model = SentenceTransformer(
            s.embedding_model, revision=s.embedding_revision, trust_remote_code=True,
            device=s.embedding_device,
            config_kwargs={"use_flash_attn": False, "fused_bias_fc": False,
                           "fused_dropout_add_ln": False, "use_xentropy": False},
        )
        if model.get_sentence_embedding_dimension() != s.embedding_dimension:
            raise ValueError("Model embedding dimension does not match configuration")
        model.max_seq_length = s.embedding_max_tokens
        model.eval()
        self._model = model

    def encode_code(self, texts: list[str], *, batch_size: int | None = None) -> list[list[float]]:
        return self._encode(texts, query=False, batch_size=batch_size)

    def encode_queries(self, texts: list[str], *, batch_size: int | None = None) -> list[list[float]]:
        return self._encode(texts, query=True, batch_size=batch_size)

    def _encode(self, texts: list[str], *, query: bool,
                batch_size: int | None = None) -> list[list[float]]:
        batch_size = self.settings.embedding_batch_size if batch_size is None else batch_size
        if batch_size not in (4, 8, 16):
            raise ValueError("Embedding batch size must be 4, 8, or 16")
        if len(texts) > batch_size:
            raise ValueError("Embedding call exceeds configured batch size")
        if any(not isinstance(t, str) or not t.strip() or len(t) > 32000 for t in texts):
            raise ValueError("Invalid or oversized embedding input")
        if not texts:
            return []
        self.load()
        vectors = self._model.encode(
            texts, prompt=self.QUERY_PREFIX if query else "",
            batch_size=batch_size, show_progress_bar=False,
            convert_to_numpy=True, normalize_embeddings=False,
        ).tolist()
        if len(vectors) != len(texts) or any(
                len(v) != self.settings.embedding_dimension
                or not all(math.isfinite(x) for x in v) for v in vectors):
            raise ValueError("Invalid embedding output shape or values")
        return vectors
