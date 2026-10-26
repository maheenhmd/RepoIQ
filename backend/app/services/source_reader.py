
import base64
import binascii

from app.integrations.github_client import GitHubClientError
from app.integrations.github_contents import get_github_file

from app.services.file_filter import (
    MAX_FILE_SIZE,
    is_relevant_file,
)


def fetch_source_file(url: str, path: str) -> dict:
    """Retrieve and decode one eligible source file."""

    # Reject disallowed filenames before calling GitHub.
    if not is_relevant_file({"path": path, "size": 1}):
        raise GitHubClientError(
            422, "This file type or path is not allowed"
        )

    repo_path = url.removeprefix("https://github.com/")
    owner, repo = repo_path.split("/")

    data = get_github_file(owner, repo, path)

    if not isinstance(data, dict) or data.get("type") != "file":
        raise GitHubClientError(
            422, "The requested path is not a regular file"
        )

    if data.get("path") != path:
        raise GitHubClientError(
            422, "GitHub returned an unexpected file path"
        )

    # Recheck against the real size returned by GitHub.
    if not is_relevant_file({
        "path": path,
        "size": data.get("size"),
    }):
        raise GitHubClientError(
            422, "File is empty, too large, or not allowed"
        )

    encoded_content = data.get("content")

    if (
        data.get("encoding") != "base64"
        or not isinstance(encoded_content, str)
    ):
        raise GitHubClientError(
            422, "Unsupported GitHub file encoding"
        )

    try:
        clean_base64 = "".join(encoded_content.split())
        raw_content = base64.b64decode(
            clean_base64,
            validate=True,
        )

    except (binascii.Error, ValueError) as exc:
        raise GitHubClientError(
            502, "Invalid Base64 content from GitHub"
        ) from exc

    if len(raw_content) > MAX_FILE_SIZE:
        raise GitHubClientError(
            422, "Decoded file exceeds the size limit"
        )

    try:
        content = raw_content.decode("utf-8")

    except UnicodeDecodeError as exc:
        raise GitHubClientError(
            422, "File is not valid UTF-8 text"
        ) from exc

    return {
        "full_name": f"{owner}/{repo}",
        "path": path,
        "sha": data["sha"],
        "size": len(raw_content),
        "content": content,
    }
