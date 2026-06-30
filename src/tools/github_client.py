import time
from typing import Any
import httpx
from src.config import settings


class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self):
        self.token = settings.github_token
        self.default_owner = settings.github_default_owner
        self.default_repo = settings.github_default_repo
        self._client = httpx.Client(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        self.call_count = 0

    def request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        path = self._resolve_path(path)
        self.call_count += 1
        start = time.time()
        response = self._client.request(method, path, **kwargs)
        elapsed_ms = int((time.time() - start) * 1000)

        if response.status_code == 403 and "rate limit" in response.text.lower():
            raise RateLimitError(response.text)
        if response.status_code == 422:
            raise ValidationError(response.status_code, response.json())
        if response.status_code >= 400:
            raise GitHubAPIError(response.status_code, response.text)

        result = response.json() if response.content else {}
        if isinstance(result, list):
            return {"items": result, "_meta": {"elapsed_ms": elapsed_ms, "status": response.status_code}}
        if isinstance(result, dict):
            result["_meta"] = {"elapsed_ms": elapsed_ms, "status": response.status_code}
        return result

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        return self.request("GET", path, params=params)

    def post(self, path: str, json_data: dict | None = None) -> dict[str, Any]:
        return self.request("POST", path, json=json_data)

    def patch(self, path: str, json_data: dict | None = None) -> dict[str, Any]:
        return self.request("PATCH", path, json=json_data)

    def delete(self, path: str) -> dict[str, Any]:
        return self.request("DELETE", path)

    def _resolve_path(self, path: str) -> str:
        return path.replace("{owner}", self.default_owner).replace("{repo}", self.default_repo)

    def reset_counter(self):
        count = self.call_count
        self.call_count = 0
        return count


class GitHubAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API {status_code}: {message}")


class RateLimitError(GitHubAPIError):
    def __init__(self, message: str):
        super().__init__(429, message)


class ValidationError(GitHubAPIError):
    def __init__(self, status_code: int, body: dict):
        self.body = body
        msg = body.get("message", str(body))
        super().__init__(status_code, msg)
