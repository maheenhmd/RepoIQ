"""Repository search orchestration with one lazily loaded encoder per process."""

import ast
import logging
import re
import textwrap
import traceback
from functools import lru_cache
from pathlib import Path
from threading import Lock

from app.core.config import get_vector_settings
from app.db import search as storage
from app.services.embeddings import EmbeddingService
from app.services.reranker import rerank

_encoder_lock = Lock()
logger = logging.getLogger(__name__)

DEFAULT_CANDIDATE_POOL_SIZE = 20
DEFAULT_IMPLEMENTATION_BOOST = 0.04
DEFAULT_NON_IMPLEMENTATION_PENALTY = 0.01
IMPLEMENTATION_SYMBOLS = frozenset(
    {"function", "async_function", "method", "async_method", "constructor"}
)
SOURCE_EXTENSIONS = frozenset({".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs"})
DOCUMENTATION_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
_IMPLEMENTATION_INTENT = re.compile(
    r"\b(?:handle[ds]?|handling|implement(?:ed|ation|ing)?|work(?:s|ing)?|"
    r"behavio(?:u)?r|logic|flow|process(?:ed|es|ing)?|"
    r"parse[ds]?|parsing|validat(?:e[ds]?|ion|ing)|raise[ds]?|raising|"
    r"catch(?:es|ing)?|calculat(?:e[ds]?|ion|ing)|execut(?:e[ds]?|ion|ing))\b",
    re.IGNORECASE,
)
_DOCUMENTATION_INTENT = re.compile(
    r"\b(?:docs?|documentation|documented|readme|guide|tutorial|usage|example|"
    r"install(?:ation|ing)?|setup|changelog|history|release notes?)\b|\bhow (?:do|can) i\b",
    re.IGNORECASE,
)
_LOOKUP_INTENT = re.compile(
    r"\b(?:what (?:is|are)|define|definition|meaning|signature|"
    r"where (?:is|are).*?(?:defined|declared)|find (?:the )?(?:symbol|declaration))\b",
    re.IGNORECASE,
)


def _implementation_query(query: str) -> bool:
    return bool(_IMPLEMENTATION_INTENT.search(query)) and not (
        _DOCUMENTATION_INTENT.search(query) or _LOOKUP_INTENT.search(query)
    )
_SYNTAX_ONLY_LINE = re.compile(
    r"(?:[{}\[\]();,:]+|"
    r"(?:(?:export|default|abstract|public|private|protected|static)\s+)*"
    r"(?:class|interface|namespace|module)\s+[\w.$<>]+"
    r"(?:\s+(?:extends|implements)\s+[\w.$<>, ]+)?\s*[{:]?)"
)
_IMPORT_EXPORT_ONLY_LINE = re.compile(
    r"(?:from\s+[\w.]+\s+import\s+.+|import\s+.+|package\s+[\w.]+\s*;|"
    r"using\s+[\w.]+\s*;|export\s*(?:type\s*)?\{.*\}\s*;?|"
    r"export\s+(?:default\s+)?[\w.$]+\s*;?|(?:module\.)?exports(?:\.\w+)?\s*=\s*[\w.$]+\s*;?)"
)
_DECLARATION_ONLY_CHUNK = re.compile(
    r"(?s)(?:class|interface)\s+[\w.$<>]+(?:\([^)]*\))?"
    r"(?:\s+(?:extends|implements)\s+[^:{]+)?\s*(?::\s*(?:pass|\.\.\.)|\{\s*\})\s*;?"
)


def _safe_traceback(exc: Exception) -> str:
    """Format traceback locations without exception text, source, or locals."""
    lines = ["Traceback (most recent call last):"]
    frames = list(traceback.walk_tb(exc.__traceback__))[-16:]
    for frame, line_number in frames:
        path = Path(frame.f_code.co_filename)
        parts = path.parts
        if "app" in parts:
            path_label = "/".join(parts[parts.index("app"):])
        elif "site-packages" in parts:
            path_label = "/".join(parts[parts.index("site-packages") + 1:])
        else:
            path_label = path.name
        lines.append(f'  File "{path_label}", line {line_number}, in {frame.f_code.co_name}')
    exception_type = f"{type(exc).__module__}.{type(exc).__name__}"
    lines.append(exception_type)
    return "\n".join(lines)


class SearchError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


@lru_cache(maxsize=1)
def get_encoder():
    return EmbeddingService(get_vector_settings())


def _content_lines(chunk: dict) -> list[str]:
    """Return non-comment content lines; Markdown headings remain searchable."""
    text = str(chunk.get("content") or "")
    extension = Path(str(chunk.get("file_path") or "")).suffix.lower()
    if extension not in SOURCE_EXTENSIONS:
        return [line.strip() for line in text.splitlines() if line.strip()]

    if extension != ".py":
        # Match quoted strings first so comment markers in URLs/literals survive.
        text = re.sub(
            r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|/\*.*?(?:\*/|$)|//[^\n]*''',
            lambda match: " " if match[0].startswith(("/*", "//")) else match[0],
            text, flags=re.DOTALL,
        )

    lines = []
    in_block_comment = False
    hash_comments = extension == ".py"
    block_comments = extension != ".py"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        while line:
            if block_comments and in_block_comment:
                end = line.find("*/")
                if end < 0:
                    line = ""
                    continue
                line = line[end + 2:].strip()
                in_block_comment = False
                continue
            if block_comments and line.startswith("/*"):
                in_block_comment = True
                line = line[2:].strip()
                continue
            if line.startswith("//") or line.startswith("#!") or (
                hash_comments and line.startswith("#")
            ):
                line = ""
                continue
            lines.append(line)
            break
    return lines


def _is_meaningful(chunk: dict) -> bool:
    lines = _content_lines(chunk)
    if not lines or not any(char.isalnum() for char in " ".join(lines)):
        return False
    tree = _python_tree(chunk)
    if tree is not None:
        return any(not (
            isinstance(node, (ast.Import, ast.ImportFrom, ast.Pass)) or
            (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
             and (node.value.value is Ellipsis or node.value.value is None
                  or isinstance(node.value.value, str) and not node.value.value.strip()))
        ) for node in tree.body)
    # Multiline JS/TS re-exports are structural even when spread over many lines.
    if re.fullmatch(r"export\s+(?:type\s+)?\{[^}]*\}\s*(?:from\s+['\"][^'\"]+['\"])?\s*;?",
                    " ".join(lines)):
        return False
    return not all(
        _SYNTAX_ONLY_LINE.fullmatch(line) or _IMPORT_EXPORT_ONLY_LINE.fullmatch(line)
        for line in lines
    )


def _python_tree(chunk: dict):
    if Path(str(chunk.get("file_path", ""))).suffix.lower() != ".py":
        return None
    try:
        return ast.parse(textwrap.dedent(chunk.get("content") or ""))
    except (SyntaxError, ValueError, RecursionError):
        return None  # Chunk boundaries can cut through an otherwise valid symbol.


def _has_implementation_body(chunk: dict) -> bool:
    if chunk.get("symbol_type") not in IMPLEMENTATION_SYMBOLS:
        return False
    tree = _python_tree(chunk)
    if tree is not None:
        functions = [node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if functions:
            return any(not (isinstance(node, ast.Pass) or (
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
            )) for function in functions for node in function.body)
    lines = _content_lines(chunk)
    return any(
        not _SYNTAX_ONLY_LINE.fullmatch(line)
        and line not in {"pass", "..."}
        and not line.startswith(("def ", "async def "))
        for line in lines[1:]
    ) or bool(lines and re.search(r"[;{}]\s*\S", lines[0]))


def _is_declaration_or_export(chunk: dict) -> bool:
    text = "\n".join(_content_lines(chunk)).strip()
    return bool(
        _DECLARATION_ONLY_CHUNK.fullmatch(text)
        or (text and all(_IMPORT_EXPORT_ONLY_LINE.fullmatch(line) for line in _content_lines(chunk)))
    )


def _is_documentation_chunk(chunk: dict) -> bool:
    path = Path(str(chunk.get("file_path") or ""))
    names = {part.lower() for part in path.parts}
    return (
        path.suffix.lower() in DOCUMENTATION_EXTENSIONS
        or bool(names & {"docs", "doc", "documentation"})
        or path.stem.lower() in {"readme", "changelog", "changes", "history", "news", "releases"}
    )


def _filtered_candidates(candidates: list[dict]) -> list[dict]:
    kept, fingerprints = [], set()
    for candidate in candidates:
        if not _is_meaningful(candidate):
            continue
        content = "\n".join(line.strip() for line in candidate['content'].splitlines() if line.strip())
        key = (candidate.get('commit_sha'), content)
        if key in fingerprints:
            continue
        # Conservative near-duplicate removal only within the same file/symbol.
        lines = set(content.splitlines())
        if len(lines) >= 8 and any(
            candidate.get('commit_sha') == prior.get('commit_sha')
            and candidate['file_path'] == prior['file_path']
            and candidate['symbol_name'] == prior['symbol_name']
            and len(lines & previous) / len(lines | previous) >= .95
            for prior, previous in kept
        ):
            continue
        fingerprints.add(key)
        kept.append((candidate, lines))
    return [candidate for candidate, _ in kept]


def _rerank_candidates(query: str, candidates: list[dict], top_k: int,
                       implementation_boost: float,
                       non_implementation_penalty: float = DEFAULT_NON_IMPLEMENTATION_PENALTY) -> list[dict]:
    prefer_implementations = _implementation_query(query)
    ranked = []
    for candidate in candidates:
        if not _is_meaningful(candidate):
            continue
        hit = dict(candidate)
        similarity = float(hit["similarity"])
        hit["similarity"] = similarity
        adjustment = 0.0
        if prefer_implementations:
            if _has_implementation_body(hit):
                adjustment = implementation_boost
            elif _is_declaration_or_export(hit) or _is_documentation_chunk(hit):
                adjustment = -non_implementation_penalty
        hit["ranking_score"] = similarity + adjustment
        hit.pop("symbol_type", None)
        ranked.append(hit)
    ranked.sort(key=lambda hit: (-hit["ranking_score"], -hit["similarity"], hit["chunk_id"]))
    return ranked[:top_k]


def _structural_tier(chunk: dict) -> int:
    """2: executable body; 1: uncertain/other evidence; 0: trivial declaration/history.

    Only used for implementation intent within the retrieved candidate pool.
    Parsing never executes repository code. Incomplete Python stays neutral.
    """
    path = Path(chunk['file_path'])
    if path.stem.lower() in {'history', 'changelog', 'changes', 'news', 'releases'}:
        return 0
    if _is_documentation_chunk(chunk):
        return 1
    tree = _python_tree(chunk)
    if tree is not None:
        functions = [node for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        def executable(node):
            if isinstance(node, (ast.Pass, ast.Import, ast.ImportFrom,
                                 ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return False
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                return False  # docstrings and ellipsis are not implementations
            if isinstance(node, ast.Raise):
                error = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
                if isinstance(error, ast.Name) and error.id == 'NotImplementedError':
                    return False
            return True
        if any(executable(node) for function in functions for node in function.body):
            return 2  # includes short returns, assignments, calls and control flow
        declarations = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        if functions or (declarations and all(
            not executable(node) for declaration in declarations for node in declaration.body
        )):
            return 0
        return 1
    if path.suffix.lower() == '.py':
        return 1
    # Without a valid AST, require symbol metadata plus explicit body operations.
    text = '\n'.join(_content_lines(chunk))
    if chunk.get('symbol_type') in IMPLEMENTATION_SYMBOLS and re.search(
        r'\{[^{}]*\b(?:return|throw|if|for|while|switch|try|await)\b', text
    ):
        return 2
    return 0 if _is_declaration_or_export(chunk) else 1


def _fuse_rankings(rankings: list[tuple[str, list[dict]]], k: int) -> list[dict]:
    fused = {}
    for source, ranking in rankings:
        weight = 3.0 if source == "filename" else 1.0
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            identity = hit['chunk_id']
            if identity in seen:
                continue
            seen.add(identity)
            result = fused.setdefault(identity, dict(hit, ranking_score=0.0))
            result['ranking_score'] += weight / (k + rank)
    return sorted(fused.values(), key=lambda hit: (-hit['ranking_score'], hit['chunk_id']))


def _prioritize_explicit_files(query: str, ranked: list[dict]) -> list[dict]:
    references = storage.explicit_file_references(query)
    if not references:
        return ranked

    def matches(hit):
        path = hit['file_path'].replace('\\', '/').lower()
        name = path.rsplit('/', 1)[-1]
        return any(
            path == reference if '/' in reference else (
                name == reference or '.' not in reference and name.startswith(reference + '.')
            ) for reference in references
        )

    if not any(matches(hit) for hit in ranked):
        return ranked
    ordered = sorted(ranked, key=lambda hit: not matches(hit))
    # Explicit filename intent is categorical. Ordinal utility keeps the public
    # score consistent with final ordering without mixing RRF, logits, or cosine.
    return [dict(hit, ranking_score=float(len(ordered) - index))
            for index, hit in enumerate(ordered)]


def _final_order(query: str, ranked: list[dict], candidates: list[dict], *, bonus=0.0) -> list[dict]:
    if not bonus or not _implementation_query(query):
        return ranked
    metadata = {hit['chunk_id']: hit for hit in candidates}
    # Only a small, score-domain-specific nudge: never partition by AST tier.
    adjusted = [dict(hit, ranking_score=hit['ranking_score'] + (
        bonus if _structural_tier(metadata[hit['chunk_id']]) == 2 else 0.0
    )) for hit in ranked]
    return sorted(adjusted, key=lambda hit: (-hit['ranking_score'], hit['chunk_id']))


def search_repository(repository_id, query, top_k, *,
                      candidate_pool_size=DEFAULT_CANDIDATE_POOL_SIZE,
                      implementation_boost=DEFAULT_IMPLEMENTATION_BOOST,
                      non_implementation_penalty=DEFAULT_NON_IMPLEMENTATION_PENALTY):
    stage = "encoder_setup"
    try:
        encoder = get_encoder()
        stage = "repository_readiness"
        ready = storage.repository_ready(repository_id, encoder.identity)
        if ready is None:
            raise SearchError("Repository not found", 404)
        if not ready:
            raise SearchError("Repository has no embeddings compatible with the configured model", 409)
        # Serialize lazy loading and CPU inference; no DB transaction stays open here.
        stage = "query_encoding"
        with _encoder_lock:
            vector = encoder.encode_queries([query])[0]
        stage = "vector_search"
        settings = get_vector_settings()
        pool_size = min(40, max(top_k, candidate_pool_size, settings.reranker_top_n))
        rankings = storage.hybrid_candidates(
            repository_id, vector, encoder.identity, query, settings.search_max_candidates,
            keyword=settings.search_keyword_enabled, symbol=settings.search_symbol_enabled,
        )
        candidates = _fuse_rankings(rankings, settings.search_rrf_k)
        scanned = len(candidates)
        filtered = _filtered_candidates(candidates)[:pool_size]
        if len(filtered) < top_k:
            logger.info("Search candidate shortage: scanned=%d usable=%d requested=%d",
                        scanned, len(filtered), top_k)
        stage = "reranking"
        ranked = rerank(query, filtered)
        bonus = settings.search_structure_logit_bonus
        if ranked is None:
            ranked = filtered
            bonus = settings.search_structure_rrf_bonus
        ranked = _final_order(query, ranked, filtered,
                              bonus=bonus if settings.search_structure_enabled else 0.0)
        chunks = _prioritize_explicit_files(query, ranked)[:top_k]
        return {"repository_id": repository_id, "chunks": chunks}
    except SearchError:
        raise
    except Exception as exc:
        # Never log the query, vector, exception message, SQL parameters, or locals.
        logger.error(
            "Code search failed during %s (%s)\n%s",
            stage,
            type(exc).__name__,
            _safe_traceback(exc),
        )
        raise SearchError("Code search is temporarily unavailable", 503) from None
