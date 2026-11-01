"""Implementation-only regressions: all external resources are mocked."""
from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.integrations.llm_client import LLMError
from app.schemas.interview import InterviewDraft, InterviewResponse, CandidateAnswer
from app.services.answer_evaluator import apply_policy, question_key
from app.services.interview_report import build_report
from app.services import question_generator as service


def draft(assessment='partial', **changes):
    data = dict(action='follow_up', topic='cache', difficulty='intermediate',
        question='How does lookup handle a cache miss?', source_ids=['S1'],
        feedback=dict(assessment=assessment, rationale='The answer omits the cache miss path.',
                      depth='reasoned', missed_concepts=['cache miss']))
    data.update(changes)
    return InterviewDraft.model_validate(data)


def state(**changes):
    return dict(dict(topic='cache', difficulty='intermediate', answer='The cache stores results.',
                     must_finish=False, correct_streak=0), **changes)


@pytest.mark.parametrize('assessment,level', [('correct', 'intermediate'), ('partial', 'intermediate'),
                                            ('incorrect', 'beginner'), ('uncertain', 'intermediate')])
def test_difficulty_policy(assessment, level):
    assert apply_policy(draft(assessment), state()).difficulty == level


def test_correct_streak_increases_one_level_and_allows_transition():
    result = apply_policy(draft('correct', action='change_topic', topic='loading'), state(correct_streak=1))
    assert result.difficulty == 'advanced'
    assert result.action == 'change_topic'


@pytest.mark.parametrize('assessment', ['partial', 'incorrect', 'uncertain'])
def test_incomplete_answers_cannot_change_topic_or_finish(assessment):
    with pytest.raises(ValueError):
        apply_policy(draft(assessment, action='change_topic', topic='other'), state())
    with pytest.raises(ValueError):
        apply_policy(draft(assessment, action='finish', question=None), state())


def test_explicit_non_answer_overrides_invented_correctness():
    result = apply_policy(draft('correct'), state(answer='I do not know'))
    assert result.feedback.assessment == 'uncertain'
    assert result.feedback.depth == 'unassessed'
    assert result.feedback.missed_concepts == []
    assert result.action == 'follow_up'


def test_irrelevant_answer_uses_existing_incorrect_assessment():
    result = apply_policy(draft('incorrect'), state(answer='My favorite food is pizza.'))
    assert result.feedback.assessment == 'incorrect'
    assert result.action == 'follow_up'


def test_turn_limit_is_authoritative_but_requires_evaluation():
    result = apply_policy(draft('partial'), state(must_finish=True))
    assert (result.action, result.question, result.topic) == ('finish', None, 'cache')
    with pytest.raises(ValueError):
        apply_policy(draft(feedback=None), state(must_finish=True))


def test_duplicate_key_ignores_case_and_punctuation():
    assert question_key('How does `lookup` work?') == question_key('HOW does lookup work!')


def history():
    session_id, repository_id = uuid4(), uuid4()
    source = dict(source_id='S1', chunk_id='a'*64, file_path='cache.py', commit_sha='b'*40,
                  symbol_name='lookup', start_line=1, end_line=2, content='def lookup():\n    return 1\n')
    first = InterviewResponse(session_id=session_id, repository_id=repository_id, commit_sha='b'*40,
        version=0, status='active', action='ask', topic='cache', difficulty='intermediate',
        question='How does lookup check a cached value?', feedback=None, sources=[source],
        topics=['cache'], answered_turns=0, max_turns=2).model_dump(mode='json')
    second = dict(first, version=1, answered_turns=1, action='change_topic', topic='loading',
                  question='How does lookup load a missing value?', feedback=dict(
                      assessment='correct', rationale='The cache lookup is correctly described.', depth='reasoned'))
    final = dict(second, version=2, answered_turns=2, status='finished', action='finish', question=None,
                 feedback=dict(assessment='partial', rationale='The answer omits how a missing value is loaded.',
                               missed_concepts=['miss path']))
    return [dict(request_id=str(uuid4()), answer=answer, response=response)
            for answer, response in [(None, first), ('Check the cache first.', second), ('I would look up the key.', final)]]


def test_report_scores_correct_question_topics_and_preserves_evidence():
    report = build_report(history())
    assert report.overall_score == report.technical_correctness == 75
    assert report.depth_score == 65
    assert report.depth_assessed_answers == 1
    assert [(x.topic, x.correctness_score) for x in report.topics] == [('cache', 100), ('loading', 50)]
    assert report.evaluations[0].question == 'How does lookup check a cached value?'
    assert report.evaluations[0].sources[0].file_path == 'cache.py'
    assert report.knowledge_gaps == ['Question 2: miss path']
    assert report.recommendations and report.strengths and report.weaknesses


def test_no_depth_in_legacy_history_is_not_invented():
    turns = history()
    turns[1]['response']['feedback'].pop('depth')
    report = build_report(turns)
    assert report.depth_score is None
    assert report.depth_assessed_answers == 0


def test_active_or_corrupt_history_does_not_produce_fake_report():
    with pytest.raises(LLMError):
        build_report(history()[:2])
    turns = history()
    turns[-1]['response']['answered_turns'] = 9
    with pytest.raises(LLMError):
        build_report(turns)


def test_report_rejects_cross_repository_history():
    turns = history()
    turns[0]['response']['repository_id'] = str(uuid4())
    with pytest.raises(LLMError):
        build_report(turns)


def test_active_report_endpoint_returns_conflict(monkeypatch):
    turns = history()[:2]
    monkeypatch.setattr(service.storage, 'load', lambda _: dict(turns=turns, version=1))
    uri = '/api/interviews/' + turns[0]['response']['session_id'] + '/report'
    assert TestClient(app).get(uri).status_code == 409


def test_unknown_citation_on_final_turn_is_not_normalized_away(monkeypatch):
    from app.core.config import InterviewSettings
    from app.schemas.interview import QuestionSource
    reference = QuestionSource(**history()[0]['response']['sources'][0])
    provider = Mock()
    provider.generate.return_value = draft(source_ids=['invented']).model_dump_json()
    with pytest.raises(LLMError) as error:
        service._generate(InterviewSettings(_env_file=None, ollama_context_tokens=32768),
                          [reference], dict(state(must_finish=True), current_question='How does lookup work?', history=[]),
                          set(), provider=provider)
    assert error.value.status_code == 502


def test_report_endpoint_reuses_durable_snapshot_without_llm(monkeypatch):
    turns = history()
    report = build_report(turns)
    turns[-1]['response']['report'] = report.model_dump(mode='json')
    monkeypatch.setattr(service.storage, 'load', lambda _: deepcopy(dict(turns=turns, version=2)))
    provider = Mock(side_effect=AssertionError('No model call permitted'))
    monkeypatch.setattr(service, 'OllamaProvider', provider)
    client = TestClient(app)
    uri = '/api/interviews/' + str(report.session_id) + '/report'
    first = client.get(uri)
    second = TestClient(app).get(uri)
    assert first.status_code == 200
    assert first.json() == second.json() == report.model_dump(mode='json')
    provider.assert_not_called()
    monkeypatch.setattr(service.storage, 'load', lambda _: None)
    assert client.get(uri).status_code == 404


def test_final_report_and_turn_are_committed_together_and_replayed(monkeypatch):
    turns = history()[:2]
    # The existing question is now the last question under a two-answer limit.
    record = dict(turns=turns, version=1)
    monkeypatch.setattr(service.storage, 'load', lambda _: deepcopy(record))
    monkeypatch.setattr(service, '_interview_context', lambda *_: [])
    from app.core.config import InterviewSettings
    monkeypatch.setattr(service, 'get_interview_settings', lambda: InterviewSettings(_env_file=None, ollama_context_tokens=32768))
    def append(request, response):
        assert response.report is not None
        assert response.report.answered_turns == 2
        record['turns'].append(dict(request_id=str(request.request_id), answer=request.answer,
                                    response=response.model_dump(mode='json')))
        record['version'] = 2
        return True
    monkeypatch.setattr(service.storage, 'append', append)
    provider = Mock()
    provider.generate.return_value = draft('partial', topic='loading').model_dump_json()
    request = CandidateAnswer(expected_version=1, answer='Check the key.')
    session_id = turns[0]['response']['session_id']
    result = service.answer_interview(session_id, request, provider=provider)
    assert result.status == 'finished'
    assert result.question is None
    assert result.report.overall_score == 75
    assert service.answer_interview(session_id, request, provider=provider) == result
    assert provider.generate.call_count == 1


def test_readiness_is_safe_and_liveness_independent(monkeypatch):
    from app.api import health
    monkeypatch.setattr(health, 'database_ready', lambda: None)
    monkeypatch.setattr(health, 'ollama_ready', lambda _: True)
    client = TestClient(app)
    assert client.get('/ready').status_code == 200
    def fail():
        raise RuntimeError('postgres://credentials-should-not-escape')
    monkeypatch.setattr(health, 'database_ready', fail)
    response = client.get('/ready')
    assert response.status_code == 503
    assert 'credentials' not in response.text
    assert client.get('/health').json() == {'status': 'ok'}
