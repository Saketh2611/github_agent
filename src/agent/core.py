import time
import json
from typing import Any
from dataclasses import dataclass, field

from supabase import create_client

from src.config import settings
from src.llm import llm
from src.tools.github_client import GitHubClient
from src.memory.execution_memory import ExecutionMemory
from src.memory.capability_memory import CapabilityMemory
from src.capabilities.synthesizer import CapabilitySynthesizer
from src.learning.feedback_loop import FeedbackLoop
from src.agent.planner import decompose_instruction
from src.agent.executor import StepExecutor


@dataclass
class ExecutionReport:
    instruction: str
    status: str
    steps_total: int
    steps_succeeded: int
    steps_failed: int
    execution_time_ms: int
    api_calls: int
    step_results: list[dict] = field(default_factory=list)
    synthesized_capabilities: list[str] = field(default_factory=list)
    optimization_applied: bool = False
    error_summary: str | None = None

    def to_dict(self) -> dict:
        return {
            "instruction": self.instruction,
            "status": self.status,
            "steps_total": self.steps_total,
            "steps_succeeded": self.steps_succeeded,
            "steps_failed": self.steps_failed,
            "execution_time_ms": self.execution_time_ms,
            "api_calls": self.api_calls,
            "step_results": self.step_results,
            "synthesized_capabilities": self.synthesized_capabilities,
            "optimization_applied": self.optimization_applied,
            "error_summary": self.error_summary,
        }


class AgentCore:
    def __init__(self):
        db = create_client(settings.supabase_url, settings.supabase_key)
        self.github = GitHubClient()
        self.execution_memory = ExecutionMemory(db)
        self.capability_memory = CapabilityMemory(db)
        self.synthesizer = CapabilitySynthesizer(self.capability_memory, self.github)
        self.feedback = FeedbackLoop(self.execution_memory, self.capability_memory)
        self.executor = StepExecutor(self.github, self.capability_memory)

    def run(self, instruction: str) -> ExecutionReport:
        """Execute a natural language instruction end-to-end."""
        start_time = time.time()
        self.github.reset_counter()

        # Phase 1: Check learning memory for optimization hints
        hints = self.feedback.get_optimization_hints(instruction)
        optimization_hint = self.feedback.suggest_decomposition(instruction, hints)

        # Phase 2: Decompose instruction into steps
        capability_summary = self.capability_memory.get_capability_summary()
        steps = decompose_instruction(instruction, capability_summary, optimization_hint)

        if not steps:
            return self._build_report(instruction, start_time, "failed", [], error="Failed to decompose instruction")

        # Phase 3: Execute steps with synthesis when needed
        step_results: list[dict] = []
        prior_results: dict[int, Any] = {}
        synthesized: list[str] = []

        for step in steps:
            step_num = step["step_number"]

            # Check dependencies
            deps = step.get("depends_on", [])
            dep_failed = any(
                prior_results.get(d, {}).get("status") == "failed"
                for d in deps
            )
            if dep_failed:
                result = {"status": "skipped", "reason": "dependency_failed"}
                step_results.append({"step": step, "result": result})
                prior_results[step_num] = result
                continue

            # Handle capability gaps
            if step.get("capability_name") == "NEEDS_SYNTHESIS":
                cap = self._attempt_synthesis(step["description"])
                if cap:
                    step["capability_name"] = cap["name"]
                    synthesized.append(cap["name"])
                else:
                    result = {"status": "failed", "error": "Capability synthesis failed"}
                    step_results.append({"step": step, "result": result})
                    prior_results[step_num] = result
                    continue

            # Execute the step
            result = self.executor.execute_step(step, prior_results)

            # If capability not found, try synthesis
            if result.get("needs_synthesis"):
                cap = self._attempt_synthesis(step["description"])
                if cap:
                    step["capability_name"] = cap["name"]
                    synthesized.append(cap["name"])
                    result = self.executor.execute_step(step, prior_results)

            step_results.append({"step": step, "result": result})
            prior_results[step_num] = result

        # Phase 4: Determine overall status
        statuses = [r["result"]["status"] for r in step_results]
        if all(s == "success" for s in statuses):
            overall_status = "success"
        elif any(s == "success" for s in statuses):
            overall_status = "partial_success"
        else:
            overall_status = "failed"

        report = self._build_report(
            instruction, start_time, overall_status, step_results,
            synthesized=synthesized,
            optimization_applied=bool(optimization_hint),
        )

        # Phase 5: Persist to execution memory
        self.execution_memory.log_execution(
            instruction=instruction,
            decomposed_steps=[s["step"] for s in step_results],
            tools_used=list({r["result"].get("capability_used", "") for r in step_results if r["result"].get("capability_used")}),
            execution_time_ms=report.execution_time_ms,
            api_calls=report.api_calls,
            status=overall_status,
            error_context=report.error_summary,
            result_summary=json.dumps([r["result"].get("data", {}) for r in step_results if r["result"].get("data")])[:2000],
        )

        return report

    def _attempt_synthesis(self, description: str) -> dict | None:
        """Try to synthesize a new capability for the described need."""
        available = self.capability_memory.get_all_capabilities()
        gap = self.synthesizer.identify_gap(description, available)
        if gap:
            return self.synthesizer.synthesize(gap)
        return self.synthesizer.synthesize(description)

    def _build_report(
        self,
        instruction: str,
        start_time: float,
        status: str,
        step_results: list[dict],
        synthesized: list[str] | None = None,
        optimization_applied: bool = False,
        error: str | None = None,
    ) -> ExecutionReport:
        elapsed = int((time.time() - start_time) * 1000)
        succeeded = sum(1 for r in step_results if r["result"]["status"] == "success")
        failed = sum(1 for r in step_results if r["result"]["status"] == "failed")

        error_summary = error
        if not error_summary:
            errors = [r["result"].get("error") for r in step_results if r["result"].get("error")]
            error_summary = "; ".join(errors) if errors else None

        return ExecutionReport(
            instruction=instruction,
            status=status,
            steps_total=len(step_results),
            steps_succeeded=succeeded,
            steps_failed=failed,
            execution_time_ms=elapsed,
            api_calls=self.github.call_count,
            step_results=step_results,
            synthesized_capabilities=synthesized or [],
            optimization_applied=optimization_applied,
            error_summary=error_summary,
        )

    def get_learning_report(self, pattern: str = "") -> dict:
        """Get the measurable improvement report."""
        return self.feedback.generate_learning_report(pattern)

    def get_memory_state(self) -> dict:
        """Return current memory state for inspection."""
        return {
            "capabilities": self.capability_memory.get_all_capabilities(),
            "capability_summary": self.capability_memory.get_capability_summary(),
        }
