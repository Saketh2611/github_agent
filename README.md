# GitHub Agent

An autonomous platform intelligence agent that executes natural language instructions against the GitHub API. It decomposes tasks into steps, synthesizes new capabilities at runtime, and learns from prior executions to improve over time.

## Features

- **Natural Language Execution** — Give instructions in plain English ("close the bug issue", "list open PRs")
- **Capability Synthesis** — When encountering an unfamiliar API operation, the agent synthesizes the correct API call at runtime
- **Learning Loop** — Tracks execution history and optimizes future runs by reusing successful strategies
- **Self-Improving** — Fewer API calls and faster execution on repeated similar instructions

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Supabase](https://supabase.com/) project (free tier works)
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
# Windows PowerShell
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 3. Install dependencies

```bash
uv pip install -e .
```

### 4. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# LLM Provider (Groq is primary, Bedrock is fallback)
GROQ_API_KEY=gsk_your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile

# AWS Bedrock (optional fallback)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=openai.gpt-oss-20b-1:0

# Supabase (for persistent memory/learning)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# GitHub
GITHUB_TOKEN=ghp_your-personal-access-token
GITHUB_DEFAULT_OWNER=your-github-username
GITHUB_DEFAULT_REPO=your-target-repo
```

**Important notes:**
- Use the **service role key** (not anon key) for `SUPABASE_KEY` to bypass RLS policies
- Your GitHub token needs `repo` scope for full access to issues, PRs, etc.
- `GITHUB_DEFAULT_OWNER` and `GITHUB_DEFAULT_REPO` are used when the instruction says "my repo"

### 5. Set up the database

Run the SQL migrations in your Supabase project (SQL Editor):

```sql
-- Run these files in order:
-- sql/001_execution_logs.sql
-- sql/002_capabilities.sql
-- sql/003_learning_metrics.sql
```

Or via the Supabase CLI:

```bash
supabase db push
```

### 6. Seed base capabilities

```bash
agent seed
```

This registers the initial set of API capabilities (list issues, create issues, update issues, comments, PRs, etc.). The agent can synthesize additional capabilities at runtime as needed.

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
