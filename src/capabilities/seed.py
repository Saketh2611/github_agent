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
        "name": "update_issue",
        "description": "Update an issue (title, body, state, labels, assignees). Use state=closed to close an issue.",
        "http_method": "PATCH",
        "endpoint_template": "/repos/{owner}/{repo}/issues/{issue_number}",
        "payload_schema": {"title": "string", "body": "string", "state": "open|closed", "labels": "array of strings", "assignees": "array of usernames"},
        "query_params_schema": None,
    },
    {
        "name": "create_issue_comment",
        "description": "Add a comment to an issue or pull request",
        "http_method": "POST",
        "endpoint_template": "/repos/{owner}/{repo}/issues/{issue_number}/comments",
        "payload_schema": {"body": "string (required)"},
        "query_params_schema": None,
    },
    {
        "name": "list_issue_comments",
        "description": "List comments on an issue",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/issues/{issue_number}/comments",
        "payload_schema": None,
        "query_params_schema": {"per_page": "int", "page": "int"},
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
        "name": "list_pulls",
        "description": "List pull requests in a repository",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/pulls",
        "payload_schema": None,
        "query_params_schema": {"state": "open|closed|all", "sort": "created|updated|popularity", "per_page": "int"},
    },
    {
        "name": "get_pull",
        "description": "Get a single pull request by number, including title, body, state, user, and diff stats",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/pulls/{pull_number}",
        "payload_schema": None,
        "query_params_schema": None,
    },
    {
        "name": "list_pull_files",
        "description": "List files changed in a pull request with additions, deletions, and patch details",
        "http_method": "GET",
        "endpoint_template": "/repos/{owner}/{repo}/pulls/{pull_number}/files",
        "payload_schema": None,
        "query_params_schema": {"per_page": "int", "page": "int"},
    },
    {
        "name": "create_pull",
        "description": "Create a pull request",
        "http_method": "POST",
        "endpoint_template": "/repos/{owner}/{repo}/pulls",
        "payload_schema": {"title": "string (required)", "body": "string", "head": "string (required)", "base": "string (required)"},
        "query_params_schema": None,
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
