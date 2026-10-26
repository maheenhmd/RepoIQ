from fastapi.testclient import TestClient

from app.main import app
from app.services.file_filter import filter_repository_files


def test_file_filter():
    files = [
        {"path": "src/main.py", "size": 120},
        {"path": "src/page.tsx", "size": 200},
        {"path": "node_modules/lib/index.js", "size": 100},
        {"path": ".env", "size": 50},
        {"path": "assets/logo.png", "size": 150},
        {"path": "src/huge.py", "size": 300000},
        {"path": "README", "size": 13},
    ]

    result = filter_repository_files(files)

    paths = [file["path"] for file in result]

    assert paths == [
        "src/main.py",
        "src/page.tsx",
        "README",
    ]


def test_filtered_files_endpoint(monkeypatch):
    def fake_discovery(url: str) -> dict:
        return {
            "full_name": "test/example",
            "branch": "main",
            "total_files": 3,
            "files": [
                {"path": "app/main.py", "size": 150},
                {"path": ".env", "size": 100},
                {"path": "images/logo.png", "size": 200},
            ],
        }

    monkeypatch.setattr(
        "app.services.repo_importer.discover_repository_files",
        fake_discovery,
    )

    client = TestClient(app)

    response = client.post(
        "/api/repositories/files/filtered",
        json={
            "url": "https://github.com/test/example"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["selected_files"] == 1
    assert data["excluded_files"] == 2
    assert data["files"][0]["path"] == "app/main.py"