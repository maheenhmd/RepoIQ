"""Mocked contract regressions; these cannot prove local-model semantic accuracy."""
import json
from unittest.mock import Mock

import pytest

from app.core.config import get_interview_settings
from app.schemas.interview import QuestionSource
from app.services.question_generator import _generate


@pytest.mark.parametrize('symbol,code,answer,assessment,rationale', [
    ('raise_for_status', 'def raise_for_status(self):\n    if 400 <= self.status_code < 600:\n        raise HTTPError()\n',
     'It raises HTTPError for 4xx client or 5xx server errors; otherwise returns None.',
     'correct', 'The answer matches the error condition and implicit return.'),
    ('lookup', 'def lookup(key):\n    return cache.get(key, None)\n',
     'It returns the cached value or None on a miss.', 'correct',
     'Both the hit behavior and missing-key default are accurately explained.'),
    ('lookup', 'def lookup(key):\n    return cache.get(key, None)\n',
     'It returns cached values.', 'partial', 'The answer omits the requested missing-key behavior.'),
    ('lookup', 'def lookup(key):\n    return cache.get(key, None)\n',
     'It always raises on a missing key.', 'incorrect', 'The claim contradicts the None default.'),
    ('lookup', 'def lookup(key):\n    return cache.get(key, None)\n',
     'I enjoy cooking.', 'incorrect', 'The answer does not address the requested lookup behavior.'),
    ('lookup', 'def lookup(key):\n    return external_lookup(key)\n',
     'It evicts stale entries.', 'uncertain', 'The external function body is absent; eviction cannot be verified.'),
])
def test_semantic_evaluation_contract(symbol, code, answer, assessment, rationale):
    source = QuestionSource(source_id='S1', chunk_id='a'*64, commit_sha='b'*40,
        file_path='module.py', symbol_name=symbol, start_line=1, end_line=3, content=code)
    question = f'What is the purpose of {symbol}?'
    provider = Mock()
    provider.generate.return_value = json.dumps(dict(action='finish', topic='implementation',
        difficulty='beginner', question=None, source_ids=['S1'],
        feedback=dict(assessment=assessment, rationale=rationale)))
    draft, refs = _generate(get_interview_settings(), [source], dict(
        topic='implementation', difficulty='intermediate', current_question=question,
        answer=answer, history=[], must_finish=True, correct_streak=0), set(), provider=provider)
    assert draft.feedback.assessment == assessment
    assert draft.difficulty == ('beginner' if assessment == 'incorrect' else 'intermediate')
    assert refs == [source]
    messages, _ = provider.generate.call_args.args
    payload = json.loads(messages[1]['content'])
    assert payload['answer'] == answer
    assert payload['current_question'] == question
    assert payload['excerpts'][0]['content'] == code
    assert 'Compare meaning' in messages[0]['content']
    assert 'Different wording' in messages[0]['content']
    provider.generate.assert_called_once()
