import subprocess
from pathlib import Path
from pydantic_settings import BaseSettings


def _detect_github_repo_from_git() -> tuple[str, str]:
    """Detect owner/repo from the current git remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "", ""
        url = result.stdout.strip()
        # Handle SSH: git@github.com:owner/repo.git
        if ":" in url and url.startswith("git@"):
            path = url.split(":")[-1]
        # Handle HTTPS: https://github.com/owner/repo.git
        elif "github.com" in url:
            path = url.split("github.com/")[-1]
        else:
            return "", ""
        path = path.removesuffix(".git")
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "", ""


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"

    database_url: str = ""

    github_token: str
    github_default_owner: str = ""
    github_default_repo: str = ""

    model_config = {
        "env_file": (
            Path.home() / ".github-agent.env",
            Path(__file__).resolve().parents[1] / ".env",
        ),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# Auto-detect from git remote if not set in .env
if not settings.github_default_owner or not settings.github_default_repo:
    _owner, _repo = _detect_github_repo_from_git()
    if _owner:
        settings.github_default_owner = _owner
    if _repo:
        settings.github_default_repo = _repo
