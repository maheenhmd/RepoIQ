"""Focused capacity and replay checks; no database/network/model execution."""
import json
from copy import deepcopy
from unittest.mock import Mock

import pytest

from test_interviews import setup, start, draft
from app.integrations.llm_client import LLMError
from app.schemas.interview import CandidateAnswer
from app.services import question_generator as service
from app.services.code_retriever import input_tokens


def test_normal_answer_final_prompt_and_replay(setup):
    settings, hit, search, records = setup
    settings.ollama_context_tokens = 4096
    request, provider, first = start()
    # Oversized candidates/history must not displace the active answer or all code.
    hit['content'] += '\n' + ('    # quoted "context" \\ repeated\n' * 300)
    provider.generate.return_value = draft('follow_up', question='How does lookup handle a cache miss?')
    answer = CandidateAnswer(expected_version=0, answer='It checks the cache for the key, returns a cached value on a hit, and loads the value on a miss.')
    result = service.answer_interview(first.session_id, answer, provider=provider)
    messages, schema = provider.generate.call_args.args
    payload = json.loads(messages[1]['content'])
    assert payload['answer'] == answer.answer
    assert payload['current_question'] == first.question
    assert any('return cache[key]' in e['content'] for e in payload['excerpts'])
    assert input_tokens(messages, schema) + settings.ollama_max_tokens + 512 <= 4096
    assert result.feedback and result.question and result.version == 1
    calls = provider.generate.call_count
    assert service.answer_interview(first.session_id, answer, provider=provider) == result
    assert provider.generate.call_count == calls
    assert len(records[first.session_id]['turns']) == 2


def test_capacity_failure_preserves_history_then_retry(setup):
    settings, hit, search, records = setup
    settings.ollama_context_tokens = 4096
    _, provider, first = start()
    before = deepcopy(records)
    answer = CandidateAnswer(expected_version=0, answer='It returns the cached value or loads a missing key.')
    settings.ollama_max_tokens = 4096
    with pytest.raises(LLMError) as failure:
        service.answer_interview(first.session_id, answer, provider=provider)
    assert failure.value.status_code == 422
    assert records == before
    settings.ollama_max_tokens = 512
    provider.generate.return_value = draft('follow_up', question='How does lookup handle a cache miss?')
    service.answer_interview(first.session_id, answer, provider=provider)
    service.answer_interview(first.session_id, answer, provider=provider)
    assert len(records[first.session_id]['turns']) == 2


def test_long_first_line_retains_partial_evidence(setup):
    settings, hit, search, records = setup
    hit['content'] = 'def lookup(key): return cache.get(key) # ' + 'context ' * 500
    sources = service._sources([hit], settings)
    assert sources and sources[0].content == hit['content'][:settings.interview_chunk_chars]
    assert sources[0].start_line == sources[0].end_line == 1


def test_single_oversized_line_fits_final_prompt(setup):
    settings, hit, search, records = setup
    settings.ollama_context_tokens = 4096
    settings.interview_chunk_chars = 6000
    settings.interview_context_chars = 6000
    hit['content'] = 'def lookup(key): return cache.get(key) # ' + 'context ' * 700
    _, provider, first = start()
    messages, schema = provider.generate.call_args.args
    evidence = json.loads(messages[1]['content'])['excerpts'][0]
    assert evidence['content'].startswith('def lookup')
    assert len(evidence['content']) < len(hit['content'])
    assert evidence['start_line'] == evidence['end_line'] == 1
    assert input_tokens(messages, schema) + 512 + settings.ollama_max_tokens <= 4096
