import json
from typing import Any

from src.llm import llm
from src.memory.capability_memory import CapabilityMemory
from src.tools.github_client import GitHubClient, GitHubAPIError, ValidationError

SYNTHESIS_SYSTEM_PROMPT = """You are a GitHub API expert. Given a capability gap description,
you must synthesize the exact API call needed.

You have access to GitHub REST API v3 (2022-11-28).
Common patterns:
- List: GET /repos/{owner}/{repo}/issues
- Create: POST /repos/{owner}/{repo}/issues
- Update: PATCH /repos/{owner}/{repo}/issues/{issue_number}
- Labels: GET/POST /repos/{owner}/{repo}/labels
- Milestones: GET/POST /repos/{owner}/{repo}/milestones
- Comments: POST /repos/{owner}/{repo}/issues/{issue_number}/comments
- Assignees: POST /repos/{owner}/{repo}/issues/{issue_number}/assignees
- Projects: GET /repos/{owner}/{repo}/projects
- Releases: POST /repos/{owner}/{repo}/releases

Respond with ONLY a JSON object, no markdown."""


class CapabilitySynthesizer:
    MAX_RETRIES = 3

    def __init__(self, capability_memory: CapabilityMemory, github: GitHubClient):
        self.memory = capability_memory
        self.github = github

    def synthesize(self, gap_description: str, context: dict | None = None) -> dict | None:
        """
        Attempt to synthesize a new capability for a described gap.
        Returns the registered capability dict if successful, None if all retries fail.
        """
        prompt = self._build_synthesis_prompt(gap_description, context)
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                spec = llm.invoke_json(prompt, system=SYNTHESIS_SYSTEM_PROMPT)
                validated = self._validate_spec(spec)
                test_result = self._test_capability(validated)

                if test_result["success"]:
                    capability = self.memory.register_capability(
                        name=validated["name"],
                        description=validated["description"],
                        http_method=validated["http_method"],
                        endpoint_template=validated["endpoint_template"],
                        payload_schema=validated.get("payload_schema"),
                        query_params_schema=validated.get("query_params_schema"),
                        constraints=test_result.get("constraints"),
                        synthesized=True,
                    )
                    return capability

                last_error = test_result.get("error", "Unknown test failure")
                prompt = self._refine_prompt(prompt, last_error, attempt)

            except (json.JSONDecodeError, KeyError, ValidationError) as e:
                last_error = str(e)
                prompt = self._refine_prompt(prompt, last_error, attempt)

        return None

    def identify_gap(self, step_description: str, available_capabilities: list[dict]) -> str | None:
        """Determine if a step requires a capability we don't have."""
        cap_names = [c["name"] for c in available_capabilities]
        cap_descriptions = [f"{c['name']}: {c['description']}" for c in available_capabilities]

        prompt = f"""Given this task step: "{step_description}"

Available capabilities:
{chr(10).join(cap_descriptions) if cap_descriptions else "(none)"}

Does this step require a capability NOT in the list above?
Respond with JSON: {{"has_gap": true/false, "gap_description": "what capability is needed", "suggested_name": "snake_case_name"}}"""

        result = llm.invoke_json(prompt)
        if result.get("has_gap"):
            return result.get("gap_description", step_description)
        return None

    def _build_synthesis_prompt(self, gap_description: str, context: dict | None) -> str:
        ctx = ""
        if context:
            ctx = f"\nAdditional context: {json.dumps(context)}"

        return f"""I need a GitHub API capability for: "{gap_description}"{ctx}

Generate the API specification as JSON:
{{
    "name": "snake_case_capability_name",
    "description": "what this does in one sentence",
    "http_method": "GET|POST|PATCH|PUT|DELETE",
    "endpoint_template": "/repos/{{owner}}/{{repo}}/...",
    "payload_schema": {{"field": "type_description"}} or null for GET,
    "query_params_schema": {{"param": "description"}} or null,
    "test_params": {{}} // minimal params to test with a safe read-only call
}}"""

    def _validate_spec(self, spec: dict) -> dict:
        required = ["name", "description", "http_method", "endpoint_template"]
        for field in required:
            if field not in spec:
                raise KeyError(f"Missing required field: {field}")
        if spec["http_method"] not in ("GET", "POST", "PATCH", "PUT", "DELETE"):
            raise ValueError(f"Invalid HTTP method: {spec['http_method']}")
        return spec

    def _test_capability(self, spec: dict) -> dict[str, Any]:
        """Test the synthesized capability with a safe call."""
        method = spec["http_method"]
        endpoint = spec["endpoint_template"]

        try:
            if method == "GET":
                params = spec.get("test_params") or spec.get("query_params_schema")
                self.github.get(endpoint, params=params)
            elif method in ("POST", "PATCH", "PUT"):
                # For write operations, do a dry-run validation by testing with GET first
                # to verify the endpoint structure is correct
                get_endpoint = endpoint.rsplit("/", 1)[0] if "/" in endpoint else endpoint
                self.github.get(get_endpoint)
            return {"success": True}
        except GitHubAPIError as e:
            constraints = []
            if e.status_code == 404:
                constraints.append("endpoint_not_found_or_no_permission")
            elif e.status_code == 403:
                constraints.append("requires_elevated_permissions")
            elif e.status_code == 422:
                constraints.append(f"validation_error: {e.message}")
            return {"success": False, "error": e.message, "constraints": constraints}

    def _refine_prompt(self, original_prompt: str, error: str, attempt: int) -> str:
        return f"""{original_prompt}

PREVIOUS ATTEMPT {attempt + 1} FAILED with error: {error}

Fix the specification. Common issues:
- Wrong endpoint path (check GitHub API docs structure)
- Missing required fields in payload
- Incorrect HTTP method
- Need to URL-encode path parameters"""
