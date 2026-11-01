from unittest.mock import Mock
from threading import BoundedSemaphore
import asyncio

import pytest

from test_interviews import setup, start, draft
from app.services import question_generator as service
from app.integrations.llm_client import LLMError
from app.schemas.interview import CandidateAnswer


@pytest.fixture(autouse=True)
def isolated_guard(monkeypatch):
    monkeypatch.setattr(service, '_generation_slot', BoundedSemaphore(1))


@pytest.mark.parametrize('failure', [LLMError('timeout', 504), RuntimeError('failure'), asyncio.CancelledError()])
def test_failure_releases_guard(failure):
    with pytest.raises(BaseException):
        with service._operation():
            raise failure
    with service._operation():
        pass


def test_active_duplicate_rejected_then_recovers():
    with service._operation():
        for _ in range(3):
            with pytest.raises(LLMError) as failure:
                with service._operation():
                    pass
            assert failure.value.status_code == 429
    with service._operation():
        pass


def test_replay_does_not_need_generation_slot(setup):
    _, provider, first = start()
    provider.generate.return_value = draft('follow_up', question='How does lookup handle a cache miss?')
    request = CandidateAnswer(expected_version=0, answer='It checks the cached value.')
    response = service.answer_interview(first.session_id, request, provider=provider)
    calls = provider.generate.call_count
    with service._operation():
        assert service.answer_interview(first.session_id, request, provider=provider) == response
    assert provider.generate.call_count == calls
    assert len(setup[3][first.session_id]['turns']) == 2


def test_failed_generation_can_retry_without_duplicate_turn(setup):
    _, provider, first = start()
    request = CandidateAnswer(expected_version=0, answer='It checks the cached value.')
    provider.generate.side_effect = LLMError('timeout', 504)
    with pytest.raises(LLMError):
        service.answer_interview(first.session_id, request, provider=provider)
    assert setup[3][first.session_id]['version'] == 0
    provider.generate.side_effect = None
    provider.generate.return_value = draft('follow_up', question='How does lookup handle a cache miss?')
    response = service.answer_interview(first.session_id, request, provider=provider)
    assert service.answer_interview(first.session_id, request, provider=provider) == response
    assert len(setup[3][first.session_id]['turns']) == 2
