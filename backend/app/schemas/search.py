from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000, strict=True)
    top_k: int = Field(default=5, ge=1, le=20, strict=True)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = value.strip()
        if not value or "\0" in value:
            raise ValueError("Provide a nonempty search query")
        return value


class SearchHit(BaseModel):
    chunk_id: str
    file_path: str
    commit_sha: str
    symbol_name: str
    start_line: int
    end_line: int
    # Raw pgvector cosine similarity remains stable for clients and diagnostics.
    similarity: float
    ranking_score: float
    content: str


class SearchResponse(BaseModel):
    repository_id: UUID
    chunks: list[SearchHit]
