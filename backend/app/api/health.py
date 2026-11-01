"""Readiness is explicit and bounded; liveness stays dependency-free."""
import json
import logging
from time import monotonic

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_interview_settings
from app.db.health import database_ready

router = APIRouter()
logger = logging.getLogger(__name__)


def ollama_ready(settings):
    # Listing installed models does not load a model, infer, or download anything.
    deadline = monotonic() + 3
    with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
        with client.stream('GET', settings.ollama_endpoint + '/api/tags') as response:
            if response.status_code != 200:
                return False
            data = bytearray()
            for part in response.iter_bytes(chunk_size=4096):
                if monotonic() > deadline or len(data) + len(part) > 65536:
                    return False
                data.extend(part)
    models = json.loads(data)['models']
    expected = settings.ollama_model
    if ':' not in expected:
        expected += ':latest'
    return any(item.get('name') == expected or item.get('model') == expected for item in models)


@router.get('/ready', responses={503: {'description': 'Database, schema, or local model unavailable'}})
def readiness():
    components = {'database': False, 'ollama_model': False}
    for name, operation in (
        ('database', database_ready),
        ('ollama_model', lambda: ollama_ready(get_interview_settings())),
    ):
        try:
            value = operation()
            components[name] = value is not False
        except Exception as exc:
            logger.warning('Readiness component=%s type=%s', name, type(exc).__name__)
    ready = all(components.values())
    return JSONResponse(status_code=200 if ready else 503,
                        content={'status': 'ready' if ready else 'unavailable', 'components': components})
