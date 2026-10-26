"""Pure source-to-chunks API; no fetching, persistence or environment settings."""

import hashlib
import json
import re
from pathlib import PurePosixPath
from uuid import UUID

from app.schemas.chunking import ChunkingOptions, ChunkingResult, CodeChunk
from app.schemas.repository import RepositoryFileRequest
from app.services.chunking.python_ast import regions
from app.services.chunking.text import SourceText, split_region
from app.services.chunking import tree_sitter_parser
from app.services.file_filter import MAX_FILE_SIZE, is_relevant_file


def chunk_source(source: str, *, repository_id: UUID, file_path: str,
                 commit_sha: str, options: ChunkingOptions | None = None) -> ChunkingResult:
    """Chunk eligible text with exact LF-normalized source coordinates.

    Metadata/options errors raise ValueError; source problems return an explicit
    empty/skipped/fallback result. Limits never produce silent partial output.
    """
    options = options or ChunkingOptions()
    repository_id = UUID(str(repository_id))
    if not isinstance(file_path, str):
        raise ValueError("file_path must be a repository-relative string")
    RepositoryFileRequest.validate_file_path(file_path)
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit_sha):
        raise ValueError("commit_sha must be a full hexadecimal Git commit SHA")
    commit_sha = commit_sha.lower()
    if not isinstance(source, str):
        raise ValueError("source must be decoded text")
    if len(source) > MAX_FILE_SIZE:
        return ChunkingResult((), "skipped", "source_size_limit")
    try:
        size = len(source.encode("utf-8"))
    except UnicodeEncodeError:
        return ChunkingResult((), "skipped", "invalid_unicode")
    if size > MAX_FILE_SIZE:
        return ChunkingResult((), "skipped", "source_size_limit")
    if "\0" in source:
        return ChunkingResult((), "skipped", "binary_content")
    if not source.strip():
        return ChunkingResult((), "empty", "empty_source")
    if not is_relevant_file({"path": file_path, "size": size}):
        return ChunkingResult((), "skipped", "excluded_file")
    text = SourceText(source)
    status, reason, strategy = "ok", None, "ast"
    version = "python-ast-v1"
    extension = PurePosixPath(file_path).suffix.lower()
    if extension == ".py":
        try:
            spans, boundaries = regions(text, options.context_chars)
        except SyntaxError as exc:
            status, reason = "fallback", f"python_syntax_error_line_{exc.lineno}"
        except (ValueError, RecursionError):
            status, reason = "fallback", "python_ast_limit"
    elif extension in tree_sitter_parser.LANGUAGES:
        strategy, version = "tree_sitter", "tree-sitter-0.13-v1"
        try:
            spans, boundaries = tree_sitter_parser.regions(
                text, options.context_chars, tree_sitter_parser.LANGUAGES[extension])
        except tree_sitter_parser.ParseFallback as exc:
            status, reason = "fallback", str(exc)
    else:
        status, reason = "fallback", "unsupported_language"
    if status == "fallback":
        strategy = "text"
        spans = [(0, len(text.text), "<file>", "text", "")]
        boundaries = []
    chunks = []
    for start, end, name, kind, context in spans:
        for begin, stop in split_region(text, start, end, budget=options.max_chars - len(context),
                                        max_lines=options.max_lines, boundaries=boundaries):
            content = text.text[begin:stop]
            if not content.strip():
                continue
            if len(chunks) >= options.max_chunks:
                return ChunkingResult((), "skipped", "chunk_count_limit")
            identity = json.dumps([version, str(repository_id), file_path, commit_sha,
                                   strategy, name, kind, begin, stop, content, context], ensure_ascii=True)
            chunks.append(CodeChunk(
                chunk_id=hashlib.sha256(identity.encode()).hexdigest(), repository_id=repository_id,
                file_path=file_path, commit_sha=commit_sha, symbol_name=name, symbol_type=kind,
                start_line=text.line(begin), end_line=text.line(stop - 1),
                start_offset=begin, end_offset=stop, content=content, context=context,
                strategy=strategy, chunk_index=len(chunks), chunker_version=version,
            ))
    return ChunkingResult(tuple(chunks), status, reason)
