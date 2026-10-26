
from pathlib import PurePosixPath
from time import sleep

from app.integrations.github_client import GitHubClientError
from app.services.repo_importer import discover_filtered_repository_files
from app.services.source_reader import fetch_source_file


MAX_BATCH_FILES = 10
MAX_BATCH_BYTES = 512 * 1024

SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
    ".go", ".rs", ".cs", ".c", ".cpp", ".rb", ".sql",
}


def _file_priority(file: dict) -> tuple[int, str]:
    """Prioritize application source code over documentation."""

    path = file["path"].lower()
    suffix = PurePosixPath(path).suffix

    if (
        path.startswith(("src/", "app/", "backend/", "frontend/"))
        and suffix in SOURCE_EXTENSIONS
    ):
        priority = 0
    elif (
        suffix in SOURCE_EXTENSIONS
        and not path.startswith((".github/", "tests/", "docs/"))
    ):
        priority = 1
    elif suffix in SOURCE_EXTENSIONS:
        priority = 2
    else:
        priority = 3

    return priority, path


def collect_repository_documents(
    url: str,
    max_files: int = 5,
) -> tuple[dict, list[dict]]:
    """Fetch a small batch of repository files into memory."""

    if not 1 <= max_files <= MAX_BATCH_FILES:
        raise ValueError("max_files must be between 1 and 10")

    discovery = discover_filtered_repository_files(url)

    candidates = sorted(
        discovery["files"],
        key=_file_priority,
    )

    documents = []
    issues = []
    total_bytes = 0
    attempted = 0
    rate_limited = False

    for file in candidates[:max_files]:
        path = file["path"]
        attempted += 1

        if total_bytes + file["size"] > MAX_BATCH_BYTES:
            issues.append({
                "path": path,
                "reason": "Batch byte limit would be exceeded",
            })
            continue

        document = None

        for attempt in range(2):
            try:
                document = fetch_source_file(url, path)
                break

            except GitHubClientError as exc:
                # Retry temporary errors only once.
                if attempt == 0 and exc.status_code in (502, 504):
                    sleep(0.5)
                    continue

                issues.append({
                    "path": path,
                    "reason": str(exc),
                })

                # Never keep requesting during rate limiting.
                if exc.status_code == 503:
                    rate_limited = True

                break

        if rate_limited:
            break

        if document is None:
            continue

        if total_bytes + document["size"] > MAX_BATCH_BYTES:
            issues.append({
                "path": path,
                "reason": "Decoded content exceeds batch byte limit",
            })
            continue

        documents.append(document)
        total_bytes += document["size"]

    summary = {
        "full_name": discovery["full_name"],
        "total_files": discovery["total_files"],
        "eligible_files": discovery["selected_files"],
        "batch_limit": max_files,
        "fetched_files": len(documents),
        "remaining_files": len(candidates) - attempted,
        "total_bytes": total_bytes,
        "files": [
            {
                "path": item["path"],
                "size": item["size"],
                "sha": item["sha"],
            }
            for item in documents
        ],
        "issues": issues,
        "rate_limited": rate_limited,
        "saved_to_database": False,
    }

    return summary, documents
