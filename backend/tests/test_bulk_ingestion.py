
from fastapi.testclient import TestClient

from app.integrations.github_client import GitHubClientError
from app.main import app
from app.services.bulk_ingestor import collect_repository_documents


client = TestClient(app)


def fake_discovery(url):
    return {
        "full_name": "psf/requests",
        "total_files": 4,
        "selected_files": 3,
        "files": [
            {"path": "README.md", "size": 20},
            {"path": "src/requests/api.py", "size": 10},
            {"path": "src/requests/auth.py", "size": 10},
        ],
    }


def test_batch_ingestion(monkeypatch):
    monkeypatch.setattr(
        "app.services.bulk_ingestor.discover_filtered_repository_files",
        fake_discovery,
    )

    def fake_fetch(url, path):
        return {
            "path": path,
            "size": 10,
            "sha": "test-sha",
            "content": "SECRET-CODE",
        }

    monkeypatch.setattr(
        "app.services.bulk_ingestor.fetch_source_file",
        fake_fetch,
    )

    response = client.post(
        "/api/repositories/ingest/preview",
        json={
            "url": "https://github.com/psf/requests",
            "max_files": 2,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["fetched_files"] == 2
    assert data["remaining_files"] == 1
    assert data["saved_to_database"] is False
    assert data["files"][0]["path"] == "src/requests/api.py"
    assert "SECRET-CODE" not in response.text


def test_rate_limit_stops_batch(monkeypatch):
    monkeypatch.setattr(
        "app.services.bulk_ingestor.discover_filtered_repository_files",
        fake_discovery,
    )

    calls = []

    def fake_fetch(url, path):
        calls.append(path)

        if path == "src/requests/auth.py":
            raise GitHubClientError(503, "Rate limit reached")

        return {
            "path": path,
            "size": 10,
            "sha": "test-sha",
            "content": "hello",
        }

    monkeypatch.setattr(
        "app.services.bulk_ingestor.fetch_source_file",
        fake_fetch,
    )

    summary, documents = collect_repository_documents(
        "https://github.com/psf/requests",
        max_files=3,
    )

    assert summary["rate_limited"] is True
    assert summary["fetched_files"] == 1
    assert len(documents) == 1
    assert calls == [
        "src/requests/api.py",
        "src/requests/auth.py",
    ]


def test_batch_limit_validation():
    response = client.post(
        "/api/repositories/ingest/preview",
        json={
            "url": "https://github.com/psf/requests",
            "max_files": 50,
        },
    )

    assert response.status_code == 422
