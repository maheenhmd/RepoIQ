"""No real database, network, model downloads or inference."""
import json
from copy import deepcopy
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import InterviewSettings
from app.integrations.llm_client import LLMError, OllamaProvider
from app.main import app
from app.schemas.interview import StartInterview, CandidateAnswer
from app.services import question_generator as service
from app.services.code_search import SearchError


def draft(action='ask', **changes):
    payload = dict(action=action, topic='caching', difficulty='intermediate',
        question=None if action == 'finish' else 'How does cache lookup avoid repeated work?',
        feedback=None if action == 'ask' else dict(assessment='partial', rationale='The cache lookup is described but the miss case is missing.'),
        source_ids=['S1'])
    payload.update(changes)
    return json.dumps(payload)


@pytest.fixture
def setup(monkeypatch):
    settings = InterviewSettings(_env_file=None, ollama_context_tokens=32768)
    monkeypatch.setattr(service, 'get_interview_settings', lambda: settings)
    hit = dict(chunk_id='a' * 64, commit_sha='b' * 40, file_path='cache.py', symbol_name='lookup',
               start_line=1, end_line=4, content='def lookup(key):\n    if key in cache:\n        return cache[key]\n    return load(key)\n')
    search = Mock(return_value=dict(chunks=[hit]))
    monkeypatch.setattr(service, 'search_repository', search)
    records = {}

    def create(request, response):
        if response.session_id in records:
            return False
        records[response.session_id] = dict(initial_request=request.model_dump(mode='json'), version=0,
            turns=[dict(request_id=str(request.request_id), answer=None, response=response.model_dump(mode='json'))])
        return True

    def append(request, response):
        record = records[response.session_id]
        if record['version'] != request.expected_version:
            return False
        record['version'] = response.version
        record['turns'].append(dict(request_id=str(request.request_id), answer=request.answer,
                                   response=response.model_dump(mode='json')))
        return True

    monkeypatch.setattr(service.storage, 'load', lambda key: deepcopy(records.get(key)))
    monkeypatch.setattr(service.storage, 'create', create)
    monkeypatch.setattr(service.storage, 'append', append)
    return settings, hit, search, records


def start():
    request = StartInterview(repository_id=uuid4(), topic='caching', max_turns=3)
    provider = Mock()
    provider.generate.return_value = draft()
    return request, provider, service.start_interview(request, provider=provider)


def test_start_reuses_scoped_search_and_canonical_citations(setup):
    settings, hit, search, records = setup
    request, provider, response = start()
    assert search.call_args_list[0].args == (request.repository_id, 'caching', 20)
    assert response.sources[0].file_path == 'cache.py'
    assert response.sources[0].commit_sha == hit['commit_sha']
    messages, schema = provider.generate.call_args.args
    assert 'UNTRUSTED DATA' in messages[0]['content']
    assert schema['properties']['source_ids']['items']['enum'] == ['S1']
    assert service.start_interview(request, provider=provider) == response
    assert provider.generate.call_count == 1
    assert records[response.session_id]['version'] == 0


@pytest.mark.parametrize('action', ['follow_up', 'change_topic', 'finish'])
def test_adaptive_decisions_and_restart_history(setup, action):
    request, provider, first = start()
    payload = json.loads(draft(action))
    if action != 'follow_up':
        payload['feedback']['assessment'] = 'correct'
    payload['question'] = None if action == 'finish' else 'What happens when lookup encounters a missing key?'
    if action == 'change_topic':
        payload['topic'] = 'loading'
        payload['difficulty'] = 'advanced'
    provider.generate.return_value = json.dumps(payload)
    answer = CandidateAnswer(expected_version=0, answer='It checks the cache first.')
    response = service.answer_interview(first.session_id, answer, provider=provider)
    assert response.action == action
    assert response.version == response.answered_turns == 1
    assert response.status == ('finished' if action == 'finish' else 'active')
    assert response.feedback.assessment == ('partial' if action == 'follow_up' else 'correct')
    assert service.answer_interview(first.session_id, answer, provider=Mock()) == response
    history = service.get_interview(first.session_id)
    assert history.current == response
    assert history.turns[1].answer == answer.answer
    assert history.turns[0].response.question == first.question
    state = json.loads(provider.generate.call_args.args[0][1]['content'])
    assert state['current_question'] == first.question
    assert state['answer'] == answer.answer


@pytest.mark.parametrize('bad', ['not json', json.dumps(dict(action='finish')),
    draft(source_ids=['invented']), draft(file_path='invented.py')])
def test_invalid_generation_never_persists(setup, bad):
    provider = Mock()
    provider.generate.return_value = bad
    with pytest.raises(LLMError) as error:
        service.start_interview(StartInterview(repository_id=uuid4(), topic='caching'), provider=provider)
    assert error.value.status_code == 502
    assert not setup[3]


def test_stale_answer_and_request_reuse_rejected(setup):
    request, provider, first = start()
    with pytest.raises(LLMError, match='version changed'):
        service.answer_interview(first.session_id, CandidateAnswer(expected_version=1, answer='Answer'), provider=provider)
    with pytest.raises(LLMError, match='different interview'):
        service.start_interview(request.model_copy(update={'topic': 'other'}), provider=provider)
    assert provider.generate.call_count == 1


def test_turn_limit_and_concurrent_cas_failure_do_not_advance(setup, monkeypatch):
    request, provider, first = start()
    setup[3][first.session_id]['turns'][0]['response']['max_turns'] = 1
    provider.generate.return_value = draft('follow_up').replace('How does cache lookup avoid repeated work?', 'What occurs on a cache miss?')
    answer = CandidateAnswer(expected_version=0, answer='Cache lookup.')
    final = service.answer_interview(first.session_id, answer, provider=provider)
    assert final.status == 'finished'
    assert final.question is None
    assert final.report.answered_turns == 1
    request, provider, first = start()
    setup[3][first.session_id]['turns'][0]['response']['max_turns'] = 1
    provider.generate.return_value = draft('finish')
    monkeypatch.setattr(service.storage, 'append', lambda *_: False)
    with pytest.raises(LLMError, match='version changed'):
        service.answer_interview(first.session_id, answer, provider=provider)
    assert setup[3][first.session_id]['version'] == 0


def test_context_limits_commit_filter_and_history_pairing(setup):
    settings, hit, _, _ = setup
    settings = settings.model_copy(update={'interview_chunk_chars': 60})
    refs = service._sources([hit, dict(hit, chunk_id='other', commit_sha='different')], settings)
    assert len(refs) == 1
    assert len(refs[0].content) <= 60
    assert refs[0].end_line == len(refs[0].content.splitlines())
    turns = [dict(answer=None, response=dict(question='First question?', topic='one', feedback=None)),
             dict(answer='First answer', response=dict(question='Second question?', topic='two', feedback=None))]
    history = service._history(turns, 1000)
    assert history[1]['question'] == 'First question?'
    assert history[1]['answer'] == 'First answer'
    assert history[1]['next_question'] == 'Second question?'


def test_empty_context_and_missing_repository(setup):
    setup[2].return_value = dict(chunks=[])
    with pytest.raises(LLMError) as error:
        start()
    assert error.value.status_code == 409
    setup[2].side_effect = SearchError('Repository not found', 404)
    with pytest.raises(SearchError) as error:
        start()
    assert error.value.status_code == 404
    assert not setup[3]


def test_database_failure_is_safe_and_does_not_claim_success(setup, monkeypatch):
    monkeypatch.setattr(service.storage, 'create', Mock(side_effect=RuntimeError('postgres://secret/source')))
    with pytest.raises(LLMError) as error:
        start()
    assert error.value.status_code == 503
    assert 'secret' not in str(error.value)


def test_ollama_schema_options_and_safe_unavailable_errors():
    settings = InterviewSettings(_env_file=None)

    def respond(request):
        body = json.loads(request.content)
        assert body['stream'] is False
        assert body['format'] == {'type': 'object'}
        assert body['options']['num_predict'] == settings.ollama_max_tokens
        return httpx.Response(200, json={'done': True, 'done_reason': 'stop', 'message': {'content': '{}'}})

    provider = OllamaProvider(settings, transport=httpx.MockTransport(respond))
    assert provider.generate([], {'type': 'object'}) == '{}'
    for response, code in [(httpx.Response(503, text='private model info'), 503),
                           (httpx.Response(200, json={'done': True, 'done_reason': 'length'}), 502)]:
        provider = OllamaProvider(settings, transport=httpx.MockTransport(lambda _: response))
        with pytest.raises(LLMError) as error:
            provider.generate([], {})
        assert error.value.status_code == code
        assert 'private' not in str(error.value)


@pytest.mark.parametrize('exception,code', [(httpx.ConnectError('secret'), 503), (httpx.ReadTimeout('secret'), 504)])
def test_ollama_transport_failures(exception, code):
    def fail(_):
        raise exception
    with pytest.raises(LLMError) as error:
        OllamaProvider(InterviewSettings(_env_file=None), transport=httpx.MockTransport(fail)).generate([], {})
    assert error.value.status_code == code
    assert 'secret' not in str(error.value)


def test_api_validation_and_safe_errors(monkeypatch):
    client = TestClient(app)
    assert client.post('/api/interviews/start', json={'repository_id': str(uuid4()), 'topic': ' ', 'max_turns': 21}).status_code == 422
    monkeypatch.setattr(service, 'start_interview', Mock(side_effect=LLMError('Local question model is unavailable', 503)))
    response = client.post('/api/interviews/start', json={'repository_id': str(uuid4()), 'topic': 'cache'})
    assert response.status_code == 503
    assert response.json() == {'detail': 'Local question model is unavailable'}


def test_duplicate_answer_request_and_finished_session(setup):
    _, provider, first = start()
    provider.generate.return_value = draft('finish', feedback={
        'assessment': 'correct', 'rationale': 'The candidate correctly explains cache lookup.'})
    answer = CandidateAnswer(expected_version=0, answer='A lookup checks the cache.')
    final = service.answer_interview(first.session_id, answer, provider=provider)
    assert final.status == 'finished'
    with pytest.raises(LLMError, match='another turn'):
        service.answer_interview(first.session_id, answer.model_copy(update={'answer': 'Changed answer'}), provider=provider)
    with pytest.raises(LLMError, match='finished'):
        service.answer_interview(first.session_id, CandidateAnswer(expected_version=1, answer='Another answer'), provider=provider)
    assert provider.generate.call_count == 2


def test_busy_generation_is_bounded(setup):
    service._generation_slot.acquire()
    try:
        with pytest.raises(LLMError) as error:
            start()
        assert error.value.status_code == 429
    finally:
        service._generation_slot.release()


def test_prompt_packing_keeps_valid_source_ranges(setup):
    settings, hit, _, _ = setup
    settings = settings.model_copy(update={'ollama_context_tokens': 8192})
    refs = service._sources([dict(hit, content='value = 1\n' * 400, end_line=400)], settings)
    provider = Mock()
    provider.generate.return_value = draft()
    _, citations = service._generate(settings, refs, dict(topic='caching', difficulty='intermediate',
        current_question=None, answer=None, must_finish=False, history=[{'answer': 'x' * 12000}]),
        set(), provider=provider)
    state = json.loads(provider.generate.call_args.args[0][1]['content'])
    assert state['history'] == []
    assert citations[0].end_line == len(citations[0].content.splitlines())


def test_sql_append_guards_version_and_commits_turn_atomically(monkeypatch):
    from unittest.mock import MagicMock
    from app.db import interviews as storage
    from app.schemas.interview import InterviewResponse
    from sqlalchemy.dialects import postgresql

    session = MagicMock()
    session.__enter__.return_value = session
    transaction = session.begin.return_value
    monkeypatch.setattr(storage, 'SessionLocal', lambda: session)
    session_id = uuid4()
    answer = CandidateAnswer(expected_version=0, answer='Cache lookup.')
    response = InterviewResponse(session_id=session_id, repository_id=uuid4(), commit_sha='b' * 40,
        version=1, status='finished', action='finish', topic='caching', difficulty='intermediate',
        question=None, feedback=None, sources=[], topics=['caching'], answered_turns=1, max_turns=3)
    session.scalar.return_value = session_id
    assert storage.append(answer, response) is True
    sql = str(session.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert 'interview_sessions.version =' in sql
    assert 'interview_sessions.status =' in sql
    assert 'interview_sessions.id =' in sql
    session.add.assert_called_once()
    transaction.__exit__.assert_called_once_with(None, None, None)
    session.reset_mock()
    session.scalar.return_value = None
    assert storage.append(answer, response) is False
    session.add.assert_not_called()
    session.scalar.return_value = session_id
    session.add.side_effect = RuntimeError('simulated insert failure')
    with pytest.raises(RuntimeError):
        storage.append(answer, response)
    assert transaction.__exit__.call_args.args[0] is RuntimeError


def test_implementation_context_retries_history_only_results(setup):
    settings, hit, search, _ = setup
    history = dict(hit, chunk_id='history', file_path='HISTORY.md')
    search.side_effect = [dict(chunks=[history]), dict(chunks=[history, hit])]
    chunks = service._interview_context(uuid4(), 'HTTP authentication and error handling', settings)
    assert chunks == [hit]
    assert search.call_count == 2


def test_documentation_interview_preserves_history(setup):
    settings, hit, search, _ = setup
    history = dict(hit, file_path='HISTORY.md')
    search.return_value = dict(chunks=[history])
    assert service._interview_context(uuid4(), 'release history documentation', settings) == [history]
    search.assert_called_once()


def test_history_only_implementation_fails_safely(setup):
    settings, hit, search, _ = setup
    search.return_value = dict(chunks=[dict(hit, file_path='HISTORY.md')])
    with pytest.raises(LLMError) as error:
        service._interview_context(uuid4(), 'authentication', settings)
    assert error.value.status_code == 409


def test_question_topic_and_code_guard(setup):
    settings, hit, _, _ = setup
    refs = service._sources([hit], settings)
    assert not service._question_relevant('What changed between old versions?', 'caching', refs)
    assert not service._question_relevant('How does authentication work?', 'caching', refs)
    assert service._question_relevant('How does lookup use the cache?', 'caching', refs)


def test_interview_env_path_is_launch_directory_independent(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.chdir(tmp_path)
    configured = Path(InterviewSettings.model_config['env_file'])
    assert configured.is_absolute()
    assert configured == Path(__file__).resolve().parents[1] / '.env'


def test_cpu_limits_are_sent_to_ollama_without_retries():
    settings = InterviewSettings(_env_file=None, ollama_model='qwen2.5-coder:1.5b',
        ollama_timeout_seconds=180, ollama_max_tokens=512, ollama_context_tokens=4096)
    calls = []
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        assert body['model'] == settings.ollama_model
        assert body['options']['num_ctx'] == 4096
        assert body['options']['num_predict'] == 512
        return httpx.Response(200, json={'done': True, 'message': {'content': '{}'}})
    provider = OllamaProvider(settings, transport=httpx.MockTransport(respond))
    assert provider.generate([], {'type': 'object'}) == '{}'
    assert len(calls) == 1


def test_first_turn_schema_forbids_feedback_and_pins_state(setup):
    request, provider, response = start()
    schema = provider.generate.call_args.args[1]
    assert schema['properties']['feedback'] == {'type': 'null'}
    assert schema['properties']['action']['const'] == 'ask'
    assert schema['properties']['topic']['const'] == request.topic
    assert schema['properties']['difficulty']['const'] == request.difficulty
    assert '$defs' not in schema


def test_invented_first_turn_feedback_still_rejected(setup):
    provider = Mock()
    provider.generate.return_value = draft(feedback={'assessment': 'correct', 'rationale': 'Invented assessment before any answer.'})
    with pytest.raises(LLMError) as error:
        service.start_interview(StartInterview(repository_id=uuid4(), topic='caching'), provider=provider)
    assert error.value.status_code == 502
    assert not setup[3]


def test_fenced_complete_json_is_parsed_but_citations_stay_validated(setup):
    provider = Mock()
    provider.generate.return_value = chr(96)*3 + 'json\n' + draft() + '\n' + chr(96)*3
    response = service.start_interview(StartInterview(repository_id=uuid4(), topic='caching'), provider=provider)
    assert response.sources[0].file_path == 'cache.py'


def test_qualified_method_reference_accepts_natural_question(setup):
    settings, hit, _, _ = setup
    refs = service._sources([dict(hit, symbol_name='Response.raise_for_status',
        content='def raise_for_status(self):\n    raise HTTPError()\n', end_line=2)], settings)
    assert service._question_relevant(
        'What is the purpose of the raise_for_status method in the Response class?',
        'HTTP authentication and error handling', refs)
    assert not service._question_relevant(
        'How does an unrelated_method work?', 'HTTP authentication', refs)


def test_same_topic_change_is_a_followup_not_a_protocol_failure(setup):
    _, provider, first = start()
    provider.generate.return_value = draft('change_topic',
        question='How does lookup handle a missing cache key?')
    response = service.answer_interview(first.session_id,
        CandidateAnswer(expected_version=0, answer='I do not know.'), provider=provider)
    assert response.action == 'follow_up'
    assert response.topic == first.topic
    assert response.sources
