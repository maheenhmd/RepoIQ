from unittest.mock import Mock
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.main import app
from app.db.search import search_statement
from app.services import code_search


def test_query_encoding_and_repository_forwarding(monkeypatch):
    repository_id = uuid4()
    encoder = Mock(identity="model-v1")
    encoder.encode_queries.return_value = [[0.1] * 768]
    monkeypatch.setattr(code_search, "get_encoder", lambda: encoder)
    ready = Mock(return_value=True)
    nearest = Mock(return_value=[("semantic", []), ("keyword", []), ("symbol", [])])
    monkeypatch.setattr(code_search.storage, "repository_ready", ready)
    monkeypatch.setattr(code_search.storage, "hybrid_candidates", nearest)
    monkeypatch.setattr(code_search, "rerank", lambda *args: None)
    assert code_search.search_repository(repository_id, "HTTP errors", 5)["chunks"] == []
    ready.assert_called_once_with(repository_id, "model-v1")
    encoder.encode_queries.assert_called_once_with(["HTTP errors"])
    encoder.encode_code.assert_not_called()
    settings = code_search.get_vector_settings()
    nearest.assert_called_once_with(repository_id, [0.1] * 768, "model-v1", "HTTP errors",
                                   settings.search_max_candidates,
                                   keyword=settings.search_keyword_enabled,
                                   symbol=settings.search_symbol_enabled)


@pytest.mark.parametrize('content', ['', ' \n\t', 'import os\nfrom pathlib import Path',
                                     'pass', '...', '# comment only', '"   "'])
def test_active_filter_rejects_low_value_python(content):
    assert code_search._filtered_candidates([_hit('noise', .9, content, 'module')]) == []


@pytest.mark.parametrize('query,first', [
    ('How are HTTP errors handled?', 'method'),
    ('What is HTTPError?', 'declaration'),
    ('How does error handling work according to documentation?', 'declaration'),
])
def test_active_final_ranking_uses_small_intent_preference(query, first):
    declaration = dict(_hit('declaration', .82, 'class HTTPError(Exception): pass', 'class'),
                       ranking_score=.0301)
    method = dict(_hit('method', .79, 'def raise_for_status(self):\n    raise HTTPError()', 'method'),
                  ranking_score=.0300)
    hits = [declaration, method]
    ranked = code_search._final_order(query, hits, hits, bonus=.0002)
    assert ranked[0]['chunk_id'] == first
    assert {hit['chunk_id']: hit['similarity'] for hit in ranked} == {'declaration': .82, 'method': .79}
    assert hits[1]['ranking_score'] == .0300


def test_structure_cannot_override_large_relevance_gap():
    docs = dict(_hit('guide', .9, '# Usage guide', file_path='README.md'), ranking_score=1.0)
    short = dict(_hit('short', .5, 'def value(): return 1', 'function'), ranking_score=-3.0)
    assert code_search._filtered_candidates([docs, short]) == [docs, short]
    assert code_search._final_order('How is value calculated?', [docs, short], [docs, short],
                                    bonus=.1)[0]['chunk_id'] == 'guide'


def test_all_hybrid_branches_keep_repository_model_isolation(monkeypatch):
    session = Mock()
    session.execute.return_value.mappings.return_value = []
    @contextmanager
    def scope():
        yield session
    monkeypatch.setattr(code_search.storage, 'request_session', scope)
    repository_id = uuid4()
    code_search.storage.hybrid_candidates(repository_id, [.1] * 768, 'model-v1', 'Response.json', 20)
    assert session.execute.call_count == 3
    for call in session.execute.call_args_list:
        compiled = call.args[0].compile(dialect=postgresql.dialect())
        where = str(compiled).split('WHERE')[1]
        assert 'code_chunks.repository_id =' in where
        assert 'code_chunks.embedding_model =' in where
        assert compiled.params['repository_id_1'] == repository_id
        assert compiled.params['embedding_model_1'] == 'model-v1'


@pytest.mark.parametrize(('query', 'expected'), [
    ('What does the project README say about usage?', ['readme']),
    ('Read CONTRIBUTING.md before changes', ['contributing.md']),
    ('Explain config in pyproject.toml', ['pyproject.toml']),
    ('Compare docs/setup.md and README', ['docs/setup.md', 'readme']),
    ('Review project history and changes', []),
    ('How does Response.json work?', []),
])
def test_explicit_filename_detection(query, expected):
    assert code_search.storage.explicit_file_references(query) == expected


def test_explicit_filename_branch_is_repository_scoped(monkeypatch):
    session = Mock()
    session.execute.return_value.mappings.return_value = []
    @contextmanager
    def scope():
        yield session
    monkeypatch.setattr(code_search.storage, 'request_session', scope)
    repository_id = uuid4()
    rankings = code_search.storage.hybrid_candidates(
        repository_id, [.1] * 768, 'model-v1', 'Read README.md usage', 20)
    assert [source for source, _ in rankings] == ['semantic', 'keyword', 'symbol', 'filename']
    filename_query = session.execute.call_args_list[-1].args[0]
    compiled = filename_query.compile(dialect=postgresql.dialect())
    where = str(compiled).split('WHERE')[1]
    assert 'code_chunks.repository_id =' in where
    assert 'code_chunks.embedding_model =' in where
    assert compiled.params['repository_id_1'] == repository_id
    assert compiled.params['embedding_model_1'] == 'model-v1'


def test_explicit_filename_match_enters_pool_and_outranks_unrelated_docs():
    readme = dict(_hit('readme', .20, '# Usage\nInstall with pip.', file_path='README.md'),
                  ranking_score=0.0)
    unrelated = dict(_hit('guide', .90, '# Advanced guide', file_path='docs/advanced.md'),
                     ranking_score=0.0)
    fused = code_search._fuse_rankings([
        ('semantic', [unrelated]), ('keyword', [unrelated]), ('filename', [readme])
    ], 60)
    assert fused[0]['chunk_id'] == 'readme'
    final = code_search._prioritize_explicit_files(
        'What does README say about usage?', [unrelated, readme])
    assert [hit['chunk_id'] for hit in final] == ['readme', 'guide']
    assert final[0]['similarity'] == .20
    assert final[0]['ranking_score'] > final[1]['ranking_score']


def test_ordinary_implementation_query_keeps_existing_order():
    method = dict(_hit('method', .8, 'def parse():\n    return value', 'function'), ranking_score=.4)
    docs = dict(_hit('docs', .9, '# Parsing', file_path='README.md'), ranking_score=.3)
    ranked = [method, docs]
    assert code_search._prioritize_explicit_files('How is parsing implemented?', ranked) == ranked


def _hit(chunk_id, similarity, content, symbol_type="text", file_path="src/example.py"):
    return {
        "chunk_id": chunk_id, "file_path": file_path, "commit_sha": "a" * 40,
        "symbol_name": chunk_id, "symbol_type": symbol_type,
        "start_line": 1, "end_line": 3, "similarity": similarity, "content": content,
    }


def test_implementation_query_prefers_substantive_method_and_filters_empty_chunks():
    candidates = [
        _hit("empty", .99, "  \n", "module"),
        _hit("exception", .82, "class HTTPError(RequestException):\n    pass", "class"),
        _hit("exports", .825, "export { HTTPError };", "module", "src/index.ts"),
        _hit("history", .81, "HTTP errors are now raised consistently.", file_path="HISTORY.md"),
        _hit("raise_for_status", .79,
             "def raise_for_status(self):\n    if http_error_msg:\n        raise HTTPError(http_error_msg)",
             "method", "requests/models.py"),
    ]
    results = code_search._rerank_candidates(
        "How are HTTP errors handled?", candidates, 3, implementation_boost=.04)
    assert [hit["chunk_id"] for hit in results] == ["raise_for_status", "exception", "history"]
    assert results[0]["similarity"] == .79
    assert results[0]["ranking_score"] == pytest.approx(.83)


def test_documentation_query_keeps_docs_ranked_by_cosine_similarity():
    candidates = [
        _hit("guide", .80, "Proxy configuration and usage guide.", file_path="docs/proxies.md"),
        _hit("configure_proxy", .79,
             "def configure_proxy(config):\n    return build_proxy(config)", "function"),
    ]
    results = code_search._rerank_candidates(
        "How does proxy configuration work according to the documentation?",
        candidates, 2, implementation_boost=.04)
    assert [hit["chunk_id"] for hit in results] == ["guide", "configure_proxy"]
    assert all(hit["ranking_score"] == hit["similarity"] for hit in results)


def test_syntax_only_chunk_is_excluded():
    candidates = [
        _hit("shell", .95, "class UserService {\n}", "class", "src/user.ts"),
        _hit("punctuation", .94, "{\n}\n;", "module", "src/user.ts"),
    ]
    assert code_search._rerank_candidates("Find user services", candidates, 5, .04) == []


@pytest.mark.parametrize(("content", "file_path"), [
    ("# only a Python comment\n# and another", "src/example.py"),
    ("// only a TypeScript comment\n/* block comment */", "src/example.ts"),
    ("/* first line\n * middle line\n */", "src/Example.java"),
])
def test_comments_only_source_chunks_are_excluded(content, file_path):
    candidate = _hit("comments", .95, content, "module", file_path)
    assert code_search._rerank_candidates("Find implementation", [candidate], 5, .04) == []


def test_markdown_heading_is_not_treated_as_a_source_comment():
    candidate = _hit("docs", .80, "# Retry behavior\nRetries use exponential backoff.",
                     file_path="docs/retries.md")
    results = code_search._rerank_candidates("retry documentation", [candidate], 5, .04)
    assert [hit["chunk_id"] for hit in results] == ["docs"]


def test_generic_implementation_intent_prefers_executable_logic():
    candidates = [
        _hit("declaration", .84, "class ParseFailure(Exception): pass", "class"),
        _hit("changes", .83, "Parser behavior changed in this release.", file_path="CHANGELOG.md"),
        _hit("parser", .80, "def parse(value):\n    return decoder.decode(value)", "function"),
    ]
    results = code_search._rerank_candidates("How does parsing work?", candidates, 3, .04)
    assert results[0]["chunk_id"] == "parser"
    assert results[0]["similarity"] == .80
    assert results[0]["ranking_score"] == pytest.approx(.84)


def test_sql_enforces_repository_and_model_isolation():
    first, second = uuid4(), uuid4()
    for target, excluded in ((first, second), (second, first)):
        compiled = search_statement(target, [0.1] * 768, "model-v1", 5).compile(
            dialect=postgresql.dialect())
        sql = str(compiled)
        assert "code_chunks.repository_id =" in sql.split("WHERE")[1]
        assert "code_chunks.embedding IS NOT NULL" in sql
        assert "code_chunks.embedding_model =" in sql
        assert "<=>" in sql and "ORDER BY" in sql and "LIMIT" in sql
        assert compiled.params["repository_id_1"] == target
        assert excluded not in [v for v in compiled.params.values() if not isinstance(v, list)]


@pytest.mark.parametrize("ready,status", [(None, 404), (False, 409)])
def test_unavailable_repository_does_not_load_model(monkeypatch, ready, status):
    encoder = Mock(identity="model-v1")
    monkeypatch.setattr(code_search, "get_encoder", lambda: encoder)
    monkeypatch.setattr(code_search.storage, "repository_ready", lambda *args: ready)
    response = TestClient(app).post(f"/api/repositories/{uuid4()}/search", json={"query": "errors"})
    assert response.status_code == status
    encoder.encode_queries.assert_not_called()


@pytest.mark.parametrize("body", [
    {"query": " "}, {"query": "x" * 2001}, {"query": "errors", "top_k": 0},
    {"query": "errors", "top_k": 21}, {"query": "errors", "top_k": True},
])
def test_invalid_input(body):
    assert TestClient(app).post(f"/api/repositories/{uuid4()}/search", json=body).status_code == 422


def test_errors_do_not_expose_database_details(monkeypatch):
    monkeypatch.setattr(code_search, "get_encoder", Mock(side_effect=RuntimeError("secret password")))
    response = TestClient(app).post(f"/api/repositories/{uuid4()}/search", json={"query": "errors"})
    assert response.status_code == 503
    assert "secret" not in response.text
