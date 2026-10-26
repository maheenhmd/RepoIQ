"""Bounded GitHub reads for the durable worker; legacy previews stay unchanged."""

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from urllib.parse import quote

import httpx

from app.core.config import Settings


class IngestionFetchError(Exception):
    def __init__(self, message: str, *, code: str = "invalid_response",
                 retryable: bool = False, retry_after: int = 0):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


def retry_delay(headers: httpx.Headers) -> int:
    now = datetime.now(timezone.utc)
    delays = [60]
    value = headers.get("retry-after", "")
    try:
        delays.append(int(value))
    except ValueError:
        try:
            delays.append(int((parsedate_to_datetime(value) - now).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            pass
    try:
        delays.append(int(headers.get("x-ratelimit-reset", "0")) - int(now.timestamp()))
    except ValueError:
        pass
    return min(max(delays), 86400)


def require_sha(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise IngestionFetchError("GitHub returned an invalid object SHA")
    return value


class IngestionGitHub:
    def __init__(self, settings: Settings, deadline: float):
        self.deadline = deadline
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoIQ"}
        if settings.github_token and settings.github_token.get_secret_value():
            headers["Authorization"] = f"Bearer {settings.github_token.get_secret_value()}"
        self.client = httpx.Client(headers=headers, follow_redirects=False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.client.close()

    def get(self, path: str, *, params: dict | None = None,
            max_bytes: int = 1024 * 1024) -> dict:
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise IngestionFetchError("Batch time budget reached", code="timeout", retryable=True)
        try:
            with self.client.stream("GET", "https://api.github.com/repos/" + path,
                                    params=params, timeout=min(5.0, remaining)) as response:
                if response.status_code in (403, 429):
                    # Conservatively pause on 403 too (secondary limits may lack headers).
                    raise IngestionFetchError("GitHub rate limit or access restriction",
                                              code="rate_limit", retryable=True,
                                              retry_after=retry_delay(response.headers))
                if response.status_code >= 500:
                    raise IngestionFetchError("Temporary GitHub failure", code="upstream", retryable=True)
                if not response.is_success:
                    raise IngestionFetchError("GitHub resource unavailable", code=str(response.status_code))
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=16384):
                    if monotonic() >= self.deadline:
                        raise IngestionFetchError("GitHub read time budget reached", code="timeout", retryable=True)
                    if len(body) + len(chunk) > max_bytes:
                        raise IngestionFetchError("GitHub response exceeds resource limit", code="size_limit")
                    body.extend(chunk)
            data = json.loads(body)
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            raise IngestionFetchError("GitHub connection failed", code="network", retryable=True) from exc
        except (ValueError, UnicodeDecodeError) as exc:
            raise IngestionFetchError("Invalid GitHub JSON response", retryable=True) from exc
        if not isinstance(data, dict):
            raise IngestionFetchError("Unexpected GitHub response")
        return data

    def pin(self, owner: str, name: str, ref: str) -> tuple[dict, str, str]:
        base = f"{quote(owner, safe='')}/{quote(name, safe='')}"
        metadata = self.get(base)
        if metadata.get("private") is not False:
            raise IngestionFetchError("Only public repositories are supported", code="private")
        branch = metadata.get("default_branch")
        if not isinstance(branch, str) or not 1 <= len(branch) <= 255:
            raise IngestionFetchError("Repository has no valid default branch")
        target = ref or branch
        try:
            commit = self.get(base + "/commits/" + quote(target, safe=""))
        except IngestionFetchError as exc:
            if exc.code in ("404", "422"):
                raise IngestionFetchError(
                    f"GitHub could not resolve Git ref {target!r} (HTTP {exc.code}). "
                    f"Omit ref or use null to select the default branch {branch!r}; "
                    "otherwise supply an existing branch, tag or commit SHA.",
                    code=exc.code,
                ) from exc
            raise
        return metadata, target, require_sha(commit.get("sha"))

    def tree(self, owner: str, name: str, commit: str) -> dict:
        return self.get(f"{quote(owner, safe='')}/{quote(name, safe='')}/git/trees/{require_sha(commit)}",
                        params={"recursive": "1"}, max_bytes=8 * 1024 * 1024)

    def blob(self, owner: str, name: str, item: dict) -> dict:
        # Blob SHA comes exclusively from the saved tree at the pinned commit.
        sha = require_sha(item["sha"])
        data = self.get(f"{quote(owner, safe='')}/{quote(name, safe='')}/git/blobs/{sha}",
                        max_bytes=400 * 1024)
        if data.get("sha") != sha or data.get("size") != item["size"]:
            raise IngestionFetchError("GitHub blob metadata mismatch")
        data.update(type="file", path=item["path"])
        return data
