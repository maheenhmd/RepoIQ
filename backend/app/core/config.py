from functools import lru_cache
from pathlib import Path

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SUPPORTED_POSTGRES_SCHEMES = (
    "postgres://",
    "postgresql://",
    "postgresql+psycopg://",
)


def _database_url(value: SecretStr | str) -> str:
    raw_url = value.get_secret_value() if isinstance(value, SecretStr) else value
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


class VectorSettings(BaseSettings):
    """Schema configuration, usable without database credentials."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / '.env'),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    embedding_dimension: int = Field(default=768, ge=1, le=16000)
    embedding_model: str = "nomic-ai/CodeRankEmbed"
    embedding_revision: str = "3c4b60807d71f79b43f3c4363786d9493691f8b1"
    embedding_device: str = "cpu"
    embedding_batch_size: Literal[4, 8, 16] = 4
    embedding_max_tokens: int = Field(default=1024, ge=32, le=8192)
    embedding_max_attempts: int = Field(default=3, ge=1, le=5)
    embedding_poll_seconds: int = Field(default=5, ge=1, le=60)
    reranker_enabled: bool = False
    reranker_model: Literal["cross-encoder/ms-marco-MiniLM-L4-v2"] = "cross-encoder/ms-marco-MiniLM-L4-v2"
    reranker_path: str = "models/reranker"
    reranker_top_n: int = Field(default=20, ge=20, le=40)
    reranker_max_length: int = Field(default=256, ge=64, le=512)
    reranker_batch_size: int = Field(default=1, ge=1, le=4)
    reranker_memory_limit_mb: int = Field(default=512, ge=256)
    reranker_headroom_mb: int = Field(default=220, ge=128)
    search_max_candidates: int = Field(default=100, ge=40, le=200)
    search_keyword_enabled: bool = True
    search_symbol_enabled: bool = True
    search_rrf_k: int = Field(default=60, ge=1, le=200)
    search_structure_enabled: bool = True
    search_structure_rrf_bonus: float = Field(default=0.0002, ge=0, le=0.001)
    search_structure_logit_bonus: float = Field(default=0.1, ge=0, le=0.25)


@lru_cache
def get_vector_settings() -> VectorSettings:
    return VectorSettings()


class Settings(VectorSettings):
    """Backend configuration loaded from environment variables."""

    database_url: SecretStr
    direct_database_url: SecretStr | None = None
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_max_overflow: int = Field(default=5, ge=0, le=20)
    db_pool_recycle_seconds: int = Field(default=300, ge=30)
    db_echo: bool = False
    github_token: SecretStr | None = None
    ingestion_batch_size: int = Field(default=10, ge=1, le=50)
    ingestion_batch_bytes: int = Field(default=512 * 1024, ge=204800, le=5242880)
    ingestion_batch_seconds: int = Field(default=20, ge=5, le=60)
    ingestion_max_files: int = Field(default=10000, ge=1, le=10000)
    ingestion_max_bytes: int = Field(default=50 * 1024 * 1024, ge=204800, le=104857600)
    ingestion_max_attempts: int = Field(default=3, ge=1, le=5)
    ingestion_poll_seconds: int = Field(default=2, ge=1, le=60)

    @field_validator("database_url", "direct_database_url", mode="before")
    @classmethod
    def require_postgresql(cls, value: object) -> object:
        if value is None:
            return None
        raw_url = (
            value.get_secret_value()
            if isinstance(value, SecretStr)
            else str(value)
        ).strip()
        if not raw_url.startswith(SUPPORTED_POSTGRES_SCHEMES):
            raise ValueError("A PostgreSQL connection URL is required")
        return raw_url

    @property
    def sqlalchemy_database_url(self) -> str:
        return _database_url(self.database_url)

    @property
    def sqlalchemy_direct_database_url(self) -> str:
        if self.direct_database_url is None:
            raise ValueError(
                "DIRECT_DATABASE_URL is required for database migrations"
            )
        return _database_url(self.direct_database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()


class InterviewSettings(BaseSettings):
    # Process environment still overrides this file; independent of launch directory.
    model_config = SettingsConfigDict(**{**VectorSettings.model_config,
        'env_file': str(Path(__file__).resolve().parents[2] / '.env')})
    ollama_endpoint: str = 'http://127.0.0.1:11434'
    ollama_model: str = Field(default='qwen2.5-coder:1.5b', min_length=1, max_length=200)
    ollama_timeout_seconds: int = Field(default=180, ge=5, le=180)
    ollama_max_tokens: int = Field(default=512, ge=128, le=4096)
    ollama_context_tokens: int = Field(default=4096, ge=4096, le=32768)
    interview_retrieval_count: int = Field(default=4, ge=1, le=20)
    interview_context_chars: int = Field(default=4000, ge=1000, le=20000)
    interview_chunk_chars: int = Field(default=1000, ge=200, le=6000)
    interview_history_chars: int = Field(default=6000, ge=1000, le=12000)
    interview_max_turns: int = Field(default=12, ge=1, le=20)

    @field_validator('ollama_endpoint')
    @classmethod
    def local_endpoint(cls, value):
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'}
                or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {'', '/'}):
            raise ValueError('Ollama endpoint must be a loopback HTTP(S) origin')
        return value.rstrip('/')


@lru_cache
def get_interview_settings() -> InterviewSettings:
    return InterviewSettings()
