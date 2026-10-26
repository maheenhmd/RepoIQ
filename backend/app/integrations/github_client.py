
from urllib.parse import quote

import httpx


class GitHubClientError(Exception):
    """Custom exception for GitHub API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


def get_repository_metadata(owner: str, repo: str) -> dict:
    """Fetch public GitHub repository information."""

    url = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        response = httpx.get(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "RepoIQ",
            },
            timeout=10.0,
        )

    except httpx.TimeoutException as exc:
        raise GitHubClientError(
            504, "GitHub request timed out"
        ) from exc

    except httpx.RequestError as exc:
        raise GitHubClientError(
            502, "Cannot reach GitHub API"
        ) from exc

    if response.status_code == 404:
        raise GitHubClientError(
            404, "Repository not found or not publicly accessible"
        )

    if response.status_code in (403, 429):
        raise GitHubClientError(
            503, "GitHub refused the request or rate limit was reached"
        )

    if not response.is_success:
        raise GitHubClientError(
            502, "GitHub API returned an error"
        )

    return response.json()


def get_repository_tree(owner: str, repo: str, branch: str) -> dict:
    """Fetch repository file and directory structure."""

    safe_branch = quote(branch, safe="")

    url = (
        f"https://api.github.com/repos/"
        f"{owner}/{repo}/git/trees/{safe_branch}"
    )

    try:
        response = httpx.get(
            url,
            params={"recursive": "1"},
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
            502, "Cannot reach GitHub API"
        ) from exc

    if response.status_code == 404:
        raise GitHubClientError(
            404, "Repository tree not found"
        )

    if response.status_code in (403, 429):
        raise GitHubClientError(
            503, "GitHub API limit reached or access denied"
        )

    if not response.is_success:
        raise GitHubClientError(
            502, "Could not fetch repository tree"
        )

    data = response.json()

    if data.get("truncated"):
        raise GitHubClientError(
            422, "Repository too large for complete tree discovery"
        )

    return data
