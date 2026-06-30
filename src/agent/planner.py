import json
from src.llm import llm


PLANNER_SYSTEM = """You are a task planner for a GitHub automation agent.
Given a natural language instruction, decompose it into a sequence of executable steps.

Each step must be a concrete API operation on GitHub.
Consider dependencies between steps (e.g., you need an issue number before you can comment on it).

Respond with ONLY a JSON object, no markdown."""


def decompose_instruction(instruction: str, capability_summary: str, optimization_hint: str = "") -> list[dict]:
    """Break a natural language instruction into executable steps."""
    hint_section = ""
    if optimization_hint:
        hint_section = f"\n\nOPTIMIZATION HINT (from prior successful runs):\n{optimization_hint}"

    prompt = f"""Instruction: "{instruction}"

Available capabilities:
{capability_summary}
{hint_section}

Decompose into ordered steps. Each step must have:
- "step_number": integer
- "description": what this step does
- "capability_name": which capability to use (from available list, or "NEEDS_SYNTHESIS" if none match)
- "params": dict of parameters needed
- "depends_on": list of step numbers this depends on (empty if independent)

Respond as: {{"steps": [...]}}"""

    result = llm.invoke_json(prompt, system=PLANNER_SYSTEM)
    return result.get("steps", [])
