# Architecture

## What does your memory system store, and why did you structure it that way?

The memory system has two distinct layers in PostgreSQL (Supabase):

**Execution Memory** (`execution_logs` table) stores the full trace of every instruction: the original NL prompt, how it was decomposed into steps, which capabilities were used, timing, API call count, and status. This isn't a log — the agent actively queries it to find successful approaches for similar instructions and avoid previously-failed strategies.

**Capability Memory** (`capabilities` table) stores what the agent knows how to do: each registered capability is an API operation with its HTTP method, endpoint template, payload/query schemas, success rate, and constraints discovered at runtime. Capabilities are either seeded (5 base operations) or synthesized at runtime — the `synthesized` boolean distinguishes them.

Why relational over vector-only: The learning loop requires aggregation queries (avg time over N runs, success rate trends). JSONB columns handle the dynamic parts (schemas, constraints) without schema migrations. This hybrid gives us both structured metrics and flexible capability storage.

## How does capability synthesis work in your implementation?

When the planner marks a step as `NEEDS_SYNTHESIS` (no existing capability matches), the `CapabilitySynthesizer`:

1. **Identifies the gap** — asks the LLM what operation is missing given available capabilities
2. **Generates a spec** — prompts the LLM with GitHub API patterns to produce endpoint, method, and schema
3. **Tests it** — makes a safe API call to verify the endpoint exists and is accessible
4. **Registers on success** — persists to `capabilities` table with `synthesized=true`
5. **Retries on failure** — feeds the error back into the prompt, up to 3 attempts with refined context

The synthesis is real: it happens at runtime, not design time. The agent starts with only 5 base capabilities (list/create/get issues, list repos, list labels). Everything else — updating issues, adding comments, managing milestones, creating releases — must be synthesized when first needed.

## What is your learning signal, and what does the agent do differently on run N vs run 1?

The primary learning signal is **API call reduction and execution time for repeated instruction patterns**.

On run 1: The agent decomposes from scratch, potentially synthesizes capabilities, and executes with no prior knowledge.

On run N: The `FeedbackLoop` queries execution memory for similar past instructions, extracts:
- The successful decomposition (exact steps that worked)
- Failed approaches to avoid
- Optimal capability selections (by success rate)

This is injected into the planner prompt as an optimization hint. The result: fewer API calls (skips trial-and-error), faster execution (reuses known-good decomposition), and no repeated synthesis (capability already registered).

Measurable: `agent learn` command shows first-run vs latest-run metrics with concrete numbers.
