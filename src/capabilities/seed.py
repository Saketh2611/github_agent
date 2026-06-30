"""Seed base capabilities — minimal set the agent starts with.
The agent must synthesize anything beyond these at runtime."""

from supabase import create_client
from src.config import settings
from src.memory.capability_memory import CapabilityMemory

BASE_CAPABILITIES = [
    {
        "name": "list_issues",
        "description": "List issues in a repository with optional filters",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/issues",
        "payload_schema": None,
        "query_params_schema": {"state": "open|closed|all", "labels": "comma-separated", "assignee": "username or none", "per_page": "int", "page": "int"},
    },
    {
        "name": "create_issue",
        "description": "Create a new issue in a repository",
        "http_method": "POST",
        "endpoint_template": "/repos/{owner}/{repo}/issues",
        "payload_schema": {"title": "string (required)", "body": "string", "labels": "array of strings", "assignees": "array of usernames"},
        "query_params_schema": None,
    },
    {
        "name": "get_issue",
        "description": "Get a single issue by number",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/issues/{issue_number}",
        "payload_schema": None,
        "query_params_schema": None,
    },
    {
        "name": "list_repos",
        "description": "List repositories for the authenticated user",
        "http_method": "GET",
        "endpoint_template": "/user/repos",
        "payload_schema": None,
        "query_params_schema": {"type": "all|owner|public|private", "sort": "created|updated|pushed|full_name", "per_page": "int"},
    },
    {
        "name": "list_labels",
        "description": "List labels in a repository",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/labels",
        "payload_schema": None,
        "query_params_schema": {"per_page": "int"},
    },
]


def seed_base_capabilities() -> int:
    db = create_client(settings.supabase_url, settings.supabase_key)
    memory = CapabilityMemory(db)

    count = 0
    for cap in BASE_CAPABILITIES:
        memory.register_capability(
            name=cap["name"],
            description=cap["description"],
            http_method=cap["http_method"],
            endpoint_template=cap["endpoint_template"],
            payload_schema=cap["payload_schema"],
            query_params_schema=cap["query_params_schema"],
            synthesized=False,
        )
        count += 1

    return count
