"""Bounded HTTP adapter for a separately provisioned local Ollama instance."""
import json
import logging
from time import monotonic
from typing import Protocol

import httpx

from app.core.config import InterviewSettings


logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class LLMProvider(Protocol):
    def generate(self, messages: list[dict], schema: dict) -> str: ...


class OllamaProvider:
    def __init__(self, settings: InterviewSettings, *, transport=None):
        self.settings = settings
        self.transport = transport

    def generate(self, messages: list[dict], schema: dict) -> str:
        settings = self.settings
        payload = dict(model=settings.ollama_model, messages=messages, format=schema,
                       stream=False, keep_alive='5m', options={
                           'num_predict': settings.ollama_max_tokens,
                           'num_ctx': settings.ollama_context_tokens, 'temperature': 0.2,
                       })
        started = monotonic()
        logger.info('Ollama chat request model=%r num_ctx=%d num_predict=%d timeout=%d prompt_chars=%d schema_bytes=%d',
                    settings.ollama_model, settings.ollama_context_tokens, settings.ollama_max_tokens,
                    settings.ollama_timeout_seconds, sum(len(m['content']) for m in messages),
                    len(json.dumps(schema).encode('utf-8')))
        try:
            deadline = monotonic() + settings.ollama_timeout_seconds
            with httpx.Client(timeout=settings.ollama_timeout_seconds, trust_env=False,
                              follow_redirects=False, transport=self.transport) as client:
                with client.stream('POST', settings.ollama_endpoint + '/api/chat', json=payload) as response:
                    if response.status_code != 200:
                        logger.warning('Ollama chat HTTP failure status=%d model=%r', response.status_code, settings.ollama_model)
                        raise LLMError('Local question model is unavailable', 503)
                    data = bytearray()
                    for block in response.iter_bytes(chunk_size=4096):
                        if monotonic() > deadline:
                            raise LLMError('Question generation timed out', 504)
                        if len(data) + len(block) > 65536:
                            raise LLMError('Question model returned invalid output', 502)
                        data.extend(block)
            result = json.loads(data)
            if result.get('done') is not True or result.get('done_reason') == 'length':
                raise ValueError('Incomplete generation')
            metrics = {key: result[key] for key in (
                'load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration',
                'prompt_eval_count', 'eval_count')
                if type(result.get(key)) in (int, float)}
            logger.info('Ollama chat completed elapsed_seconds=%.2f metrics=%s', monotonic() - started, metrics)
            content = result['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError('Missing content')
            return content
        except httpx.TimeoutException as exc:
            logger.warning('Ollama chat stage=timeout type=%s elapsed_seconds=%.2f limit=%d',
                           type(exc).__name__, monotonic() - started, settings.ollama_timeout_seconds)
            raise LLMError('Question generation timed out', 504) from None
        except httpx.HTTPError as exc:
            logger.warning('Ollama chat stage=transport type=%s', type(exc).__name__)
            raise LLMError('Local question model is unavailable', 503) from None
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            logger.warning('Ollama chat stage=response_validation type=%s', type(exc).__name__)
            raise LLMError('Question model returned invalid output', 502) from None
