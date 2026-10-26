
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, field_validator


class RepositoryPreviewRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())

        if (
            parsed.scheme != "https"
            or parsed.netloc.lower() != "github.com"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Enter a valid HTTPS GitHub URL")

        parts = parsed.path.strip("/").split("/")

        if len(parts) != 2:
            raise ValueError("URL must contain owner and repo")

        owner, repo = parts

        if repo.endswith(".git"):
            repo = repo[:-4]

        if not (
            re.fullmatch(r"[A-Za-z0-9-]{1,39}", owner)
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo)
        ):
            raise ValueError("Invalid repository name")

        return f"https://github.com/{owner}/{repo}"


class RepositoryPreviewResponse(BaseModel):
    full_name: str
    description: str | None
    language: str | None
    stars: int
    default_branch: str
    url: str


class RepositoryFileRequest(RepositoryPreviewRequest):
    path: str

    @field_validator("path")
    @classmethod
    def validate_file_path(cls, value: str) -> str:
        parts = value.split("/")

        if (
            not value
            or len(value) > 1000
            or value.startswith("/")
            or "\\" in value
            or any(part in ("", ".", "..") for part in parts)
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("Invalid repository file path")

        return value


class RepositoryFileContentResponse(BaseModel):
    full_name: str
    path: str
    sha: str
    size: int
    content: str
