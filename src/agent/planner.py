import json
from src.config import settings
from src.llm import llm


PLANNER_SYSTEM = """You are a task planner for a GitHub automation agent.
Given a natural language instruction, decompose it into a sequence of executable steps.

Each step must be a concrete API operation on GitHub.
Consider dependencies between steps (e.g., you need an issue number before you can comment on it).

IMPORTANT: When a capability requires "owner" and "repo" path parameters, use the default owner and repo provided in the context unless the user explicitly specifies a different one.

Respond with ONLY a JSON object, no markdown."""


def decompose_instruction(instruction: str, capability_summary: str, optimization_hint: str = "") -> list[dict]:
    """Break a natural language instruction into executable steps."""
    hint_section = ""
    if optimization_hint:
        hint_section = f"\n\nOPTIMIZATION HINT (from prior successful runs):\n{optimization_hint}"

    default_context = ""
    if settings.github_default_owner or settings.github_default_repo:
        default_context = f"\n\nDefault GitHub context:\n- owner: \"{settings.github_default_owner}\"\n- repo: \"{settings.github_default_repo}\"\nUse these values for {{owner}} and {{repo}} unless the user specifies otherwise."

    prompt = f"""Instruction: "{instruction}"

Available capabilities:
{capability_summary}
{hint_section}{default_context}

Decompose into the MINIMUM number of steps needed. Do NOT add redundant steps (e.g., don't "get issue details" if you already have the issue number from a list step).

Each step must have:
- "step_number": integer
- "description": what this step does
- "capability_name": which capability to use (from available list, or "NEEDS_SYNTHESIS" if none match)
- "params": dict of parameters needed (MUST include "owner" and "repo" for endpoints that require them)
- "depends_on": list of step numbers this depends on (empty if independent)

IMPORTANT: All param values MUST be valid JSON literals (strings, numbers, booleans, arrays, objects). Do NOT use JavaScript expressions, string concatenation (+), template literals, or function calls in param values.

For params referencing prior step results, use "$step_N.field" syntax (e.g., "$step_1.0.number" to get the number field from the first item in step 1's result list).
For params that need the full result from a prior step (e.g., a list of issues to format as a table), just use "$step_N" — the agent will format it appropriately.

Respond as: {{"steps": [...]}}"""

    result = llm.invoke_json(prompt, system=PLANNER_SYSTEM)
    return result.get("steps", [])
