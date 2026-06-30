# Demo Instructions

Three instructions of increasing complexity, run live:

## Instruction 1 — Simple (uses existing capabilities)

```
agent run "Create a bug report issue titled 'Login timeout on mobile' with labels bug and high-priority"
```

**Expected behavior:**
- Decomposes into 1 step: create_issue with title, body, and labels
- Uses the seeded `create_issue` capability directly
- Returns structured report with the created issue URL

## Instruction 2 — Medium (triggers capability synthesis)

```
agent run "Find all open issues with no assignee and add a comment saying 'Triaging — will assign by EOD'"
```

**Expected behavior:**
- Decomposes into 2 steps: list_issues (filtered by no assignee) → comment on each
- `list_issues` exists, but `add_comment` does NOT — triggers synthesis
- Agent synthesizes `add_issue_comment` (POST /repos/{owner}/{repo}/issues/{issue_number}/comments)
- Executes the comment on each found issue
- On second run: skips synthesis, reuses the registered capability, fewer API calls

## Instruction 3 — Complex (compound, multi-step, shows learning)

```
agent run "Find all open issues labeled 'bug', group them by priority label, and create a summary issue titled 'Weekly Bug Triage' with a markdown table of all bugs organized by priority"
```

**Expected behavior:**
- Decomposes into 3+ steps: list issues → filter/group (done in agent logic) → create summary issue
- May synthesize capabilities if needed (e.g., label-filtered listing)
- Handles the data transformation (grouping) internally
- Creates a well-formatted summary issue
- On repeated runs: uses learned decomposition, skips synthesis, measurably fewer API calls

## Showing Learning

After running instruction 3 twice:
```
agent learn "bug"
```

Shows concrete improvement:
- First run: X API calls, Y ms
- Second run: fewer API calls, less time
- Reason: agent reused successful decomposition and pre-registered synthesized capabilities
