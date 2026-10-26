from app.integrations.github_client import (
    get_repository_metadata,
    get_repository_tree,
)

from app.services.file_filter import filter_repository_files


def preview_repository(url: str) -> dict:
    repo_path = url.removeprefix("https://github.com/")
    owner, repo = repo_path.split("/")

    data = get_repository_metadata(owner, repo)

    return {
        "full_name": data["full_name"],
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data["stargazers_count"],
        "default_branch": data["default_branch"],
        "url": data["html_url"],
    }


def discover_repository_files(url: str) -> dict:
    metadata = preview_repository(url)

    repo_path = url.removeprefix("https://github.com/")
    owner, repo = repo_path.split("/")

    tree_data = get_repository_tree(
        owner,
        repo,
        metadata["default_branch"],
    )

    files = [
        {
            "path": item["path"],
            "size": item.get("size"),
        }
        for item in tree_data["tree"]
        if item.get("type") == "blob"
    ]

    return {
        "full_name": metadata["full_name"],
        "branch": metadata["default_branch"],
        "total_files": len(files),
        "files": files,
    }


def discover_filtered_repository_files(url: str) -> dict:
    """Discover and filter repository files."""

    repository = discover_repository_files(url)

    selected_files = filter_repository_files(
        repository["files"]
    )

    return {
        "full_name": repository["full_name"],
        "branch": repository["branch"],
        "total_files": repository["total_files"],
        "selected_files": len(selected_files),
        "excluded_files": (
            repository["total_files"] - len(selected_files)
        ),
        "files": selected_files,
    }