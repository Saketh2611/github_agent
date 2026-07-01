import json
import time
from typing import Any

from src.config import settings
from src.llm import llm
from src.tools.github_client import GitHubClient, GitHubAPIError
from src.memory.capability_memory import CapabilityMemory


class StepExecutor:
    def __init__(self, github: GitHubClient, capability_memory: CapabilityMemory):
        self.github = github
        self.capability_memory = capability_memory

    def execute_step(self, step: dict, prior_results: dict[int, Any]) -> dict:
        """Execute a single step using the appropriate capability."""
        cap_name = step.get("capability_name", "")
        params = self._resolve_params(step.get("params", {}), prior_results)

        capability = self.capability_memory.find_capability(cap_name)
        if not capability:
            return {
                "status": "failed",
                "error": f"Capability '{cap_name}' not found",
                "needs_synthesis": True,
            }

        method = capability["http_method"]
        endpoint = self._build_endpoint(capability["endpoint_template"], params)

        try:
            start = time.time()
            if method == "GET":
                query_params = self._extract_query_params(params, capability)
                result = self.github.get(endpoint, params=query_params)
            elif method == "POST":
                payload = self._build_payload(params, capability)
                result = self.github.post(endpoint, json_data=payload)
            elif method == "PATCH":
                payload = self._build_payload(params, capability)
                result = self.github.patch(endpoint, json_data=payload)
            elif method == "DELETE":
                result = self.github.delete(endpoint)
            else:
                return {"status": "failed", "error": f"Unsupported method: {method}"}

            elapsed = int((time.time() - start) * 1000)
            self.capability_memory.record_usage(cap_name, success=True)

            return {
                "status": "success",
                "data": self._sanitize_result(result),
                "elapsed_ms": elapsed,
                "capability_used": cap_name,
            }

        except GitHubAPIError as e:
            self.capability_memory.record_usage(
                cap_name, success=False, constraint=f"{e.status_code}: {e.message[:100]}"
            )
            return {
                "status": "failed",
                "error": str(e),
                "status_code": e.status_code,
                "capability_used": cap_name,
            }

    def _resolve_params(self, params: dict, prior_results: dict[int, Any]) -> dict:
        """Replace references to prior step outputs with actual values."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$step_"):
                parts = value.split(".")
                step_num = int(parts[0].replace("$step_", ""))
                if step_num in prior_results and prior_results[step_num].get("status") == "success":
                    data = prior_results[step_num].get("data", {})
                    # Unwrap {"items": [...]} to list for easier traversal
                    if isinstance(data, dict) and "items" in data and len(parts) > 1 and parts[1] != "items":
                        data = data["items"]
                    for part in parts[1:]:
                        if isinstance(data, dict):
                            data = data.get(part, value)
                        elif isinstance(data, list) and part.isdigit():
                            data = data[int(part)] if int(part) < len(data) else value
                        elif isinstance(data, list) and not part.isdigit():
                            # Try first item in list
                            if data and isinstance(data[0], dict):
                                data = data[0].get(part, value)
                            else:
                                break
                    resolved[key] = data
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    def _build_endpoint(self, template: str, params: dict) -> str:
        """Fill in path parameters in the endpoint template."""
        endpoint = template
        for key, value in params.items():
            placeholder = "{" + key + "}"
            if placeholder in endpoint:
                endpoint = endpoint.replace(placeholder, str(value))
        if "{owner}" in endpoint and settings.github_default_owner:
            endpoint = endpoint.replace("{owner}", settings.github_default_owner)
        if "{repo}" in endpoint and settings.github_default_repo:
            endpoint = endpoint.replace("{repo}", settings.github_default_repo)
        return endpoint

    def _extract_query_params(self, params: dict, capability: dict) -> dict | None:
        """Extract query parameters from params based on capability schema."""
        schema = capability.get("query_params_schema")
        if schema:
            schema = json.loads(schema) if isinstance(schema, str) else schema
            return {k: v for k, v in params.items() if k in schema}
        path_params = self._get_path_params(capability["endpoint_template"])
        return {k: v for k, v in params.items() if k not in path_params} or None

    def _build_payload(self, params: dict, capability: dict) -> dict:
        """Build the request payload, excluding path parameters."""
        path_params = self._get_path_params(capability["endpoint_template"])
        return {k: v for k, v in params.items() if k not in path_params}

    def _get_path_params(self, template: str) -> set:
        """Extract path parameter names from endpoint template."""
        import re
        return set(re.findall(r"\{(\w+)\}", template))

    def _sanitize_result(self, result: dict) -> dict:
        """Remove metadata and limit response size for storage."""
        if "_meta" in result:
            result = {k: v for k, v in result.items() if k != "_meta"}
        if "items" in result and isinstance(result["items"], list):
            result["items"] = result["items"][:20]
            result["_truncated"] = len(result["items"]) > 20
        return result
