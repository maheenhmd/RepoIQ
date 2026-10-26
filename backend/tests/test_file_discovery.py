import httpx
from fastapi.testclient import TestClient
from app.main import app


def test_file_discovery(monkeypatch):
    def fake_get(url, **kwargs):
        if "/git/trees/" in url:
            return httpx.Response(
                200,
                json={
                    "truncated": False,
                    "tree": [
                        {"path": "app/main.py", "type": "blob", "size": 120},
                        {"path": "app", "type": "tree"},
                    ],
                },
            )

        return httpx.Response(
            200,
            json={
                "full_name": "octocat/Hello-World",
                "description": None,
                "language": None,
                "stargazers_count": 10,
                "default_branch": "master",
                "html_url": "https://github.com/octocat/Hello-World",
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    response = TestClient(app).post(
        "/api/repositories/files",
        json={"url": "https://github.com/octocat/Hello-World"},
    )

    assert response.status_code == 200
    assert response.json()["total_files"] == 1
    assert response.json()["files"][0]["path"] == "app/main.py"