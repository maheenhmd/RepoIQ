
import base64

import httpx
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_source_file_retrieval(monkeypatch):
    source_code = b"def hello():\n    return 'Hello RepoIQ'\n"

    encoded = base64.b64encode(source_code).decode("ascii")

    def fake_get(url, **kwargs):
        assert url.endswith("/contents/src/requests/api.py")

        return httpx.Response(
            200,
            json={
                "type": "file",
                "path": "src/requests/api.py",
                "size": len(source_code),
                "sha": "test-file-sha",
                "encoding": "base64",
                "content": encoded,
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    response = client.post(
        "/api/repositories/file-content",
        json={
            "url": "https://github.com/psf/requests",
            "path": "src/requests/api.py",
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == source_code.decode("utf-8")
    assert response.json()["size"] == len(source_code)


def test_env_file_rejected():
    response = client.post(
        "/api/repositories/file-content",
        json={
            "url": "https://github.com/psf/requests",
            "path": ".env",
        },
    )

    assert response.status_code == 422


def test_path_traversal_rejected():
    response = client.post(
        "/api/repositories/file-content",
        json={
            "url": "https://github.com/psf/requests",
            "path": "../secret.py",
        },
    )

    assert response.status_code == 422
