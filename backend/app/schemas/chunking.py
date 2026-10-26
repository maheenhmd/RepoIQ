"""Immutable, storage-independent inputs and results for source chunking."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class ChunkingOptions:
    max_chars: int = 4000
    max_lines: int = 100
    context_chars: int = 600
    max_chunks: int = 2048

    def __post_init__(self) -> None:
        for name in ("max_chars", "max_lines", "context_chars", "max_chunks"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 256 <= self.max_chars <= 16000:
            raise ValueError("max_chars must be between 256 and 16000")
        if not 1 <= self.max_lines <= 500:
            raise ValueError("max_lines must be between 1 and 500")
        if not 0 <= self.context_chars <= self.max_chars // 2:
            raise ValueError("context_chars must be at most half of max_chars")
        if not 1 <= self.max_chunks <= 8192:
            raise ValueError("max_chunks must be between 1 and 8192")


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    repository_id: UUID
    file_path: str
    commit_sha: str
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int
    content: str
    context: str
    strategy: Literal["ast", "tree_sitter", "text"]
    chunk_index: int
    chunker_version: str = "python-ast-v1"


@dataclass(frozen=True)
class ChunkingResult:
    chunks: tuple[CodeChunk, ...]
    status: Literal["ok", "fallback", "empty", "skipped"]
    reason: str | None = None
