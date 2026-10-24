import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tools.pull_request_workflow import (
    PullRequestWorkflowError,
    push_workspace_changes,
    summarize_pull_request_changes,
)


class FakeGitHub:
    def __init__(self):
        self.posts = []

    def get(self, path, params=None):
        if path == "/repos/octo/project":
            return {"default_branch": "main"}
        if path.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "base-commit"}}
        if path.endswith("/git/commits/base-commit"):
            return {"tree": {"sha": "base-tree"}}
        if path.endswith("/pulls/42"):
            return {
                "number": 42,
                "html_url": "https://github.com/octo/project/pull/42",
                "title": "Improve greeting",
                "body": "Make greeting configurable.",
            }
        if path.endswith("/pulls/42/files"):
            return {
                "items": [
                    {
                        "filename": "hello.py",
                        "status": "modified",
                        "additions": 1,
                        "deletions": 1,
                        "patch": "@@ -1 +1 @@\n-print('Hello')\n+print('Hello there')",
                    }
                ]
            }
        raise AssertionError(f"Unexpected GET: {path}")

    def post(self, path, json_data=None):
        self.posts.append((path, json_data))
        if path.endswith("/git/blobs"):
            return {"sha": f"blob-{len(self.posts)}"}
        if path.endswith("/git/trees"):
            return {"sha": "new-tree"}
        if path.endswith("/git/commits"):
            return {"sha": "new-commit"}
        if path.endswith("/git/refs"):
            return {}
        if path.endswith("/pulls"):
            return {
                "number": 7,
                "html_url": "https://github.com/octo/project/pull/7",
                "title": json_data["title"],
            }
        raise AssertionError(f"Unexpected POST: {path}")


class PullRequestWorkflowTests(unittest.TestCase):
    def _git(self, root: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_pushes_workspace_changes_and_opens_pull_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "original.txt").write_text("initial", encoding="utf-8")
            self._git(root, "init", "-b", "main")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test User")
            self._git(root, "add", "original.txt")
            self._git(root, "commit", "-m", "initial")
            self._git(
                root,
                "remote",
                "add",
                "origin",
                "https://github.com/octo/project.git",
            )
            (root / "original.txt").write_text("updated", encoding="utf-8")
            (root / "removed.txt").write_text("remove me", encoding="utf-8")
            self._git(root, "add", "removed.txt")
            self._git(root, "commit", "-m", "add file to remove")
            (root / "removed.txt").unlink()
            (root / "new.py").write_text("print('hello')\n", encoding="utf-8")

            fake_github = FakeGitHub()
            with patch(
                "src.tools.pull_request_workflow._git_root", return_value=root
            ):
                result = push_workspace_changes(
                    fake_github,
                    {
                        "owner": "octo",
                        "repo": "project",
                        "title": "Add greeting",
                        "body": "Adds a greeting example.",
                        "branch": "feature/greeting",
                    },
                )

        tree_call = next(
            payload
            for path, payload in fake_github.posts
            if path.endswith("/git/trees")
        )
        entries = {entry["path"]: entry for entry in tree_call["tree"]}
        self.assertEqual(
            set(entries), {"original.txt", "removed.txt", "new.py"}
        )
        self.assertIsNone(entries["removed.txt"]["sha"])
        self.assertEqual(result["number"], 7)
        self.assertEqual(result["files_pushed"], 3)
        pull_call = next(
            payload for path, payload in fake_github.posts if path.endswith("/pulls")
        )
        self.assertEqual(pull_call["head"], "feature/greeting")
        self.assertEqual(pull_call["base"], "main")
        self.assertEqual(pull_call["body"], "Adds a greeting example.")

    def test_summarizes_pull_request_diff_with_llm(self):
        fake_github = FakeGitHub()
        with patch(
            "src.tools.pull_request_workflow.llm.invoke",
            return_value="The greeting output was updated.",
        ) as invoke:
            result = summarize_pull_request_changes(
                fake_github, "octo", "project", 42
            )

        self.assertEqual(result["explanation"], "The greeting output was updated.")
        self.assertEqual(result["files"][0]["filename"], "hello.py")
        self.assertIn("+print('Hello there')", invoke.call_args.args[0])

    def test_refuses_to_push_environment_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init", "-b", "main")
            self._git(root, "config", "user.email", "test@example.com")
            self._git(root, "config", "user.name", "Test User")
            (root / "baseline.txt").write_text("baseline", encoding="utf-8")
            self._git(root, "add", "baseline.txt")
            self._git(root, "commit", "-m", "initial")
            self._git(
                root,
                "remote",
                "add",
                "origin",
                "https://github.com/octo/project.git",
            )
            (root / ".env").write_text("SECRET=value", encoding="utf-8")
            with patch(
                "src.tools.pull_request_workflow._git_root", return_value=root
            ):
                with self.assertRaisesRegex(
                    PullRequestWorkflowError, "potentially sensitive"
                ):
                    push_workspace_changes(
                        FakeGitHub(),
                        {"owner": "octo", "repo": "project", "title": "Push"},
                    )


if __name__ == "__main__":
    unittest.main()
