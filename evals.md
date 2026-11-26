# GitHub Agent Evaluation Runs

Target repository: `Saketh2611/AI-Multi-Agent-Workflow`

These are end-to-end CLI runs using the configured local Ollama model and GitHub
credentials. Outcomes below reflect the actual agent reports, including extra
steps proposed by the planner. The create-issue run was explicitly authorized;
it created issue #14. No other GitHub content was created by these runs.

## 1. Repository overview: issues and pull requests

**Request**

> Give me a repository overview for Saketh2611/AI-Multi-Agent-Workflow: list
> open issues and open pull requests, then summarize their counts and recurring
> themes. Do not modify anything.

**Result:** Partial success (2/3 steps; 6 API calls, about 20.3 seconds). It
listed six open issues (#13, #12, #11, #10, #7, #4), but did not return a useful
overview of pull requests or themes. Despite the read-only request, the planner
added a pull-request creation step; GitHub rejected it with HTTP 422. The CLI
then crashed while rendering the error because the Windows console encoding
could not print a Unicode arrow (`UnicodeEncodeError`).

## 2. List open pull requests

**Request**

> List the open pull requests in Saketh2611/AI-Multi-Agent-Workflow. For each,
> return its number, title, state, and URL. Read-only; do not create or modify
> any GitHub content.

**Result:** Partial success (4/5 steps; 7 API calls; about 20.5 seconds). It
found open PRs #13, “Add greeting support,” and #10, “OLLAMA MODEL.” The planner
also attempted to synthesize a `create_pull` call without `base` or `head`;
GitHub rejected it with HTTP 422. It unnecessarily fetched/explained PR #13 and
repeated the PR listing. The run did not show URLs.

## 3. Create one evaluation issue

**Request**

> Create exactly one GitHub issue in Saketh2611/AI-Multi-Agent-Workflow with
> the title “EVALS” and body “Evaluation issue created to verify the GitHub
> agent issue-creation workflow. No action is required.” Do not create a pull
> request or any other issue.

**Result:** Partial success (4/10 steps; 9 API calls; about 14.1 seconds).
Exactly one requested issue was created: #14, “EVALS.” The planner also made
unnecessary calls to fetch an issue and PR details, create an issue comment,
explain a PR, and create a PR. Those extra operations failed; no extra issue or
PR was created. Overall status was partial success.

## 4. Explain PR code changes

**Request**

> Explain the code changes in pull request 13 in
> Saketh2611/AI-Multi-Agent-Workflow. Fetch its title, description, changed
> files, and diffs; explain the purpose and behavior changes in plain language.
> Do not modify anything or create GitHub content.

**Result:** Partial success (5/7 steps; 7 API calls; about 49.1 seconds). It
identified PR #13, “Add greeting support,” and fetched its description and
changed files: three modified `__pycache__` files and `agents/graph.py` (324
insertions and 324 deletions). The explanation itself was not displayed in the
CLI output. The planner additionally attempted to create an issue to track the
explanation; that request failed with HTTP 422, and the dependent comment step
was skipped.

**Code-change explanation (verified from the PR diff):** `agents/graph.py`
flattens researcher output when it is a list of content chunks, so quality
checks count characters rather than list items. It also adds retry context to
the coder, executes generated code and records success, retries coding after
execution failures up to a limit, and connects planner/researcher/coder/
executor/reporter nodes with conditional retry edges. The PR also modifies
three compiled Python cache files; those are not useful source changes.

## 5. Create a PR for this evaluation report

**Request**

> Push the current changes in evals.md to a new branch in
> Saketh2611/AI-Multi-Agent-Workflow and open a pull request titled “Add GitHub
> agent evaluation results.” Do not include any other files.

**Result:** Partial success (5/7 steps; 7 API calls; about 58.0 seconds). The
agent found the issue and open PRs, but unnecessarily tried to fetch and explain
PR #13. Its PR-creation request failed with HTTP 422, and the workspace push
was correctly refused because this checkout's Git origin is
`Saketh2611/github_agent`, not the requested target
`Saketh2611/AI-Multi-Agent-Workflow`. No PR was created. GitHub verification
confirmed that issue #14 exists and that the target still has only open PRs #13
and #10.

## Overall observations

- The issue-creation capability successfully created the one authorized issue.
- The PR explanation path fetched PR metadata and changed-file data, but the
  CLI renderer omitted the returned explanation text.
- Across the five runs, the planner repeatedly added unrelated actions despite
  explicit read-only or narrowly scoped instructions. Those extra write
  attempts were rejected; issue #14 is the only content created.
- The PR creation workflow correctly rejected a target repository that did not
  match the checkout's Git origin. To open a PR for `evals.md`, run from a
  checkout whose `origin` is `Saketh2611/AI-Multi-Agent-Workflow`.
