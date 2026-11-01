"""Read-only cosine retrieval, always restricted to a repository and model."""

import re

from sqlalchemy import case, func, or_, select

from app.db.ingestion import request_session
from app.db.models import CodeChunk, Repository


_DOCUMENT_FILE = re.compile(
    r"(?<![\w/.-])(?:[\w.-]+/)*[\w.-]+\.(?:md|mdx|rst|txt|toml|yaml|yml|ini|cfg)(?![\w.-])",
    re.IGNORECASE,
)
_NAMED_FILE = re.compile(
    r"\b(?:README|CONTRIBUTING|CHANGELOG|CHANGES|HISTORY|LICENSE|NOTICE)"
    r"(?:\.(?i:[\w.-]+))?\b",
)


def explicit_file_references(query: str) -> list[str]:
    """Extract explicit documentation/config filenames, preserving query order."""
    matches = sorted(
        (*_DOCUMENT_FILE.finditer(query), *_NAMED_FILE.finditer(query)),
        key=lambda match: match.start(),
    )
    return list(dict.fromkeys(
        match.group().replace("\\", "/").strip("./").lower() for match in matches
    ))[:8]


def eligible(repository_id, model):
    return (CodeChunk.repository_id == repository_id,
            CodeChunk.embedding.is_not(None), CodeChunk.embedding_model == model)


def repository_ready(repository_id, model):
    with request_session() as session:
        if session.scalar(select(Repository.id).where(Repository.id == repository_id)) is None:
            return None
        return session.scalar(select(CodeChunk.id).where(*eligible(repository_id, model)).limit(1)) is not None


def search_statement(repository_id, vector, model, top_k, *, offset=0):
    distance = CodeChunk.embedding.cosine_distance(vector)
    return select(
        CodeChunk.chunk_id, CodeChunk.file_path, CodeChunk.commit_sha,
        CodeChunk.symbol_name, CodeChunk.symbol_type,
        CodeChunk.start_line, CodeChunk.end_line,
        (1 - distance).label("similarity"), CodeChunk.content,
    ).where(
        *eligible(repository_id, model),
        func.length(func.btrim(CodeChunk.content, " \t\r\n")) > 0,
    ).order_by(distance, CodeChunk.chunk_id).limit(top_k).offset(offset)


def nearest_chunks(repository_id, vector, model, top_k, *, offset=0):
    with request_session() as session:
        return [dict(row) for row in session.execute(
            search_statement(repository_id, vector, model, top_k, offset=offset)).mappings()]


def hybrid_candidates(repository_id, vector, model, query, limit, *, keyword=True, symbol=True):
    """Independent rankings, with identical SQL isolation and cosine for every hit.

    FTS is computed on demand: no migration/backfill required. Existing request
    statement timeouts apply. Add expression indexes after measuring corpus scale.
    """
    base = search_statement(repository_id, vector, model, limit).order_by(None)
    rankings = []
    with request_session() as session:
        rankings.append(("semantic", [dict(row) for row in session.execute(
            search_statement(repository_id, vector, model, limit)).mappings()]))
        if keyword:
            # Split code identifiers as well as prose; no raw tsquery interpolation.
            words = re.findall(r"[^\W_]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", query))[:32]
            if words:
                document = func.to_tsvector('english', func.concat_ws(' ',
                    CodeChunk.symbol_name, CodeChunk.file_path, CodeChunk.content))
                terms = func.websearch_to_tsquery('english', ' OR '.join(words))
                statement = base.where(document.op('@@')(terms)).order_by(
                    func.ts_rank_cd(document, terms).desc(), CodeChunk.chunk_id)
                rankings.append(("keyword", [dict(row) for row in session.execute(statement).mappings()]))
        if symbol:
            names = list(dict.fromkeys(re.findall(r'[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*', query)))[:32]
            if names:
                full = CodeChunk.symbol_name.in_(names)
                leaf = func.regexp_replace(CodeChunk.symbol_name, r'^.*\.', '').in_(names)
                statement = base.where(or_(full, leaf)).order_by(
                    case((full, 0), else_=1), CodeChunk.chunk_id)
                rankings.append(("symbol", [dict(row) for row in session.execute(statement).mappings()]))
        references = explicit_file_references(query)
        if references:
            lowered = func.lower(CodeChunk.file_path)
            basename = func.regexp_replace(lowered, r'^.*/', '')
            conditions = []
            for reference in references:
                if "/" in reference:
                    conditions.append(lowered == reference)
                elif "." not in reference:
                    conditions.append(or_(basename == reference,
                                          basename.like(reference + '.%')))
                else:
                    conditions.append(basename == reference)
            # Vector order selects the most semantically relevant chunks when an
            # explicitly named long document is split into many chunks.
            statement = search_statement(repository_id, vector, model, limit).where(
                or_(*conditions)
            )
            rankings.append(("filename", [
                dict(row) for row in session.execute(statement).mappings()
            ]))
    return rankings
