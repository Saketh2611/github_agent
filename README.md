# GitHub Agent

An autonomous platform intelligence agent that executes natural language instructions against the GitHub API. It decomposes tasks into steps, synthesizes new capabilities at runtime, and learns from prior executions to improve over time.

## Features

- **Natural Language Execution** — Give instructions in plain English ("close the bug issue", "list open PRs")
- **Capability Synthesis** — When encountering an unfamiliar API operation, the agent synthesizes the correct API call at runtime
- **Pull Request Workflow** — Push current local Git changes to a new branch, open a pull request, and generate a change summary from an existing PR's diff
- **Learning Loop** — Tracks execution history and optimizes future runs by reusing successful strategies
- **Self-Improving** — Fewer API calls and faster execution on repeated similar instructions

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [GitHub Personal Access Token](https://github.com/settings/tokens)
- A [Groq API Key](https://console.groq.com/) (primary LLM) or AWS Bedrock access (fallback)

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Saketh2611/AI-Multi-Agent-Workflow.git
cd AI-Multi-Agent-Workflow
```

### 2. Create and activate virtual environment

```bash
uv venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on Linux/macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

For an installation isolated to this project's virtual environment:

```bash
uv pip install -e .
```

To install `agent` as a user-wide command that does not require activating this
project's virtual environment, run this from the repository root instead:

```powershell
uv tool install --editable .
```

Then `agent` can be run from any directory. If PowerShell does not recognize
the command immediately after installation, open a new terminal and ensure the
directory reported by `uv tool dir --bin` is on your user `PATH`.

### 4. Configure environment variables

For project-local credentials, copy the example file and fill in your values:

```bash
cp .env.example .env
```

The agent loads environment variables first, then configuration from
`%USERPROFILE%\.github-agent.env` on Windows or `~/.github-agent.env` on
Linux/macOS, followed by the `.env` next to this clone. It does not load an
unrelated `.env` from the directory where the global command is run. Keep
credential files private and out of version control.

Edit `.env` with your values:

```env
# LLM Provider (Groq is primary, Bedrock is fallback)
GROQ_API_KEY=gsk_your-groq-api-key
GROQ_MODEL=openai/gpt-oss-120b

# AWS Bedrock (optional fallback)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=openai.gpt-oss-20b-1:0

# SQLite (for persistent memory/learning)
DATABASE_URL=sqlite:///DB/github_agent.sqlite3
# Optional: use sqlite:// for a temporary in-memory database

# GitHub
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_DEFAULT_OWNER=your-github-username
GITHUB_DEFAULT_REPO=your-target-repo
```

**Important notes:**
- Your GitHub token needs `repo` scope for full access to issues, PRs, etc.
- `GITHUB_DEFAULT_OWNER` and `GITHUB_DEFAULT_REPO` are used when the instruction says "my repo"

### 5. Set up the database

The SQLite database and tables are created automatically on startup in the
`DB` folder. The default database is persistent; set `DATABASE_URL=sqlite://`
to use a temporary in-memory database instead.

### 6. Seed base capabilities

With the virtual environment activated:

```bash
agent seed
```

In Windows PowerShell, you can also run the installed command directly without
activating the environment:

```powershell
.\.venv\Scripts\agent.exe seed
```

This registers the initial set of API capabilities (list issues, create issues, update issues, comments, PRs, etc.). The agent can synthesize additional capabilities at runtime as needed.
Run `agent seed` again after updating the application to register newly added capabilities.

### Create and explain pull requests

From inside the target repository, ask the agent to push the current local
changes and open a pull request. For example:

```powershell
agent run "Push my current changes to a new branch and open a PR titled 'Add greeting support' with a description of the changes"
```

The local Git `origin` must match the target GitHub repository. Tracked changes
and non-ignored untracked files are included; deleted tracked files are
propagated. The workflow rejects likely secret files such as `.env` files and
private-key files, and does not reuse an existing branch.

To have the LLM explain a PR's code changes, include its number in the
instruction:

```powershell
agent run "Explain the code changes in PR 42"
```

## Usage

### Run an instruction

```bash
agent run "<natural language instruction>"
```

**Examples:**

```bash
# List open issues
agent run "list open issues in my repo"

# Create an issue
agent run "Create a bug report issue titled 'Login timeout on mobile' with labels bug and high-priority"

# Close an issue with a comment
agent run "close the Test Issue with the comment (test issue resolved)"

# Multi-step operations
agent run "Find all open issues labeled 'bug' and create a summary issue with a markdown table"
```

### View registered capabilities

```bash
agent capabilities
```

Shows all capabilities the agent knows about, including ones synthesized at runtime.

### View learning report

```bash
agent learn
agent learn "bug"  # filter by pattern
```

Shows execution statistics and improvement signals:
- Total runs, average time, average API calls
- Success rate over time
- First-run vs latest-run comparison
- Synthesized capabilities count

### Re-seed capabilities

If you need to reset capabilities (e.g., after schema changes):

```sql
-- Run in Supabase SQL Editor
DELETE FROM capabilities;
```

Then:

```bash
agent seed
```

## How It Works

```
User Instruction
       │
       ▼
┌─────────────┐    ┌──────────────────┐
│   Planner   │◄───│ Execution Memory │  (optimization hints from prior runs)
└─────┬───────┘    └──────────────────┘
      │ decompose into steps
      ▼
┌─────────────┐    ┌───────────────────┐
│  Executor   │◄───│ Capability Memory │  (registered API operations)
└─────┬───────┘    └───────────────────┘
      │                     ▲
      │ if capability       │ register new
      │ not found           │
      ▼                     │
┌─────────────────┐         │
│  Synthesizer    │─────────┘
│ (generates new  │
│  API calls)     │
└─────────────────┘
      │
      ▼
┌─────────────┐
│ GitHub API  │
└─────────────┘
```

1. **Planner** — Decomposes natural language into ordered API steps using the LLM
2. **Executor** — Executes each step using registered capabilities
3. **Synthesizer** — When a needed capability doesn't exist, generates and tests a new API spec
4. **Learning** — Stores execution results; future runs use optimization hints from successful past runs

## Project Structure

```
├── main.py                  # Entry point
├── src/
│   ├── cli.py              # Typer CLI commands
│   ├── config.py           # Settings from .env
│   ├── llm.py             # LLM client (Groq primary, Bedrock fallback)
│   ├── agent/
│   │   ├── core.py        # Main agent orchestration
│   │   ├── planner.py     # NL → steps decomposition
│   │   └── executor.py    # Step execution engine
│   ├── capabilities/
│   │   ├── seed.py        # Base capability definitions
│   │   └── synthesizer.py # Runtime capability generation
│   ├── memory/
│   │   ├── execution_memory.py  # Run history storage
│   │   └── capability_memory.py # Capability registry
│   ├── learning/
│   │   └── feedback_loop.py     # Optimization hints
│   └── tools/
│       └── github_client.py     # GitHub REST API client
├── sql/                    # Database migrations
├── pyproject.toml          # Dependencies
└── .env.example           # Environment template
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `Bad credentials` (401) | Regenerate your GitHub token with `repo` scope |
| `Not Found` (404) | Check `GITHUB_DEFAULT_OWNER` and `GITHUB_DEFAULT_REPO` in `.env` |
| `row-level security policy` | Use the Supabase **service role key**, not the anon key |
| `Capability synthesis failed` | Run `agent seed` to ensure base capabilities exist |
| `No LLM configured` | Set `GROQ_API_KEY` in `.env` |
| `Groq unavailable` | The client retries 3 times; check your Groq quota |

## License

MIT
