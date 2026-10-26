
from urllib.parse import quote

import httpx

from app.integrations.github_client import GitHubClientError


def get_github_file(owner: str, repo: str, path: str) -> dict:
    """Fetch one public repository file from GitHub."""

    encoded_path = quote(path, safe="/")

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/contents/{encoded_path}"
    )

    try:
        response = httpx.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "RepoIQ",
            },
            timeout=15.0,
        )

    except httpx.TimeoutException as exc:
        raise GitHubClientError(
            504, "GitHub request timed out"
        ) from exc

    except httpx.RequestError as exc:
        raise GitHubClientError(
            502, "Could not connect to GitHub"
        ) from exc

    if response.status_code == 404:
        raise GitHubClientError(
            404, "File not found or not publicly accessible"
        )

    if response.status_code in (403, 429):
        raise GitHubClientError(
            503, "GitHub API rate limit or access restriction"
        )

    if not response.is_success:
        raise GitHubClientError(
            502, "GitHub could not return the file"
        )

    return response.json()
