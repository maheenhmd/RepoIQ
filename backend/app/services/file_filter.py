from pathlib import PurePosixPath

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".go", ".rs", ".cs",
    ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".sql",
    ".html", ".css", ".sh", ".md",
}

EXCLUDED_DIRECTORIES = {
    ".git", ".venv", "venv",
    "node_modules", "__pycache__",
    ".next", "dist", "build",
    "coverage", ".pytest_cache",
    ".mypy_cache", "vendor",
    "target",
}

EXCLUDED_FILENAMES = {
    "secrets.py",
    "credentials.py",
    "id_rsa",
    "id_ed25519",
}

MAX_FILE_SIZE = 200 * 1024  # 200 KB


def is_relevant_file(file: dict) -> bool:
    """Check whether a repository file is suitable for indexing."""

    file_path = file.get("path")
    file_size = file.get("size")

    if not isinstance(file_path, str):
        return False

    if not isinstance(file_size, int):
        return False

    if not 0 < file_size <= MAX_FILE_SIZE:
        return False

    # GitHub paths use forward slashes.
    if "\\" in file_path:
        return False

    path = PurePosixPath(file_path)
    parts = [part.lower() for part in path.parts]

    if not parts or path.is_absolute() or ".." in parts:
        return False

    if any(
        part in EXCLUDED_DIRECTORIES
        for part in parts[:-1]
    ):
        return False

    filename = parts[-1]

    if filename.startswith(".env"):
        return False

    if filename in EXCLUDED_FILENAMES:
        return False

    if filename.endswith(".min.js"):
        return False

    # README without extension is useful project context.
    if filename == "readme":
        return True

    return path.suffix.lower() in ALLOWED_EXTENSIONS


def filter_repository_files(files: list[dict]) -> list[dict]:
    """Return only relevant repository files."""

    return [
        file
        for file in files
        if is_relevant_file(file)
    ]