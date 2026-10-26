from functools import lru_cache

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


class Settings(BaseSettings):
    """Backend configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

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
