import json
from src.memory.execution_memory import ExecutionMemory
from src.memory.capability_memory import CapabilityMemory
from src.llm import llm


class FeedbackLoop:
    def __init__(self, execution_memory: ExecutionMemory, capability_memory: CapabilityMemory):
        self.execution_memory = execution_memory
        self.capability_memory = capability_memory

    def get_optimization_hints(self, instruction: str) -> dict | None:
        """Check past executions and return hints for better execution."""
        stats = self.execution_memory.get_execution_stats(
            self.execution_memory._extract_keywords(instruction)
        )

        if stats["total_runs"] == 0:
            return None

        successful = self.execution_memory.get_successful_approach(instruction)
        failed = self.execution_memory.get_failed_approaches(instruction)

        hints = {
            "has_prior_runs": True,
            "total_runs": stats["total_runs"],
            "success_rate": stats["success_rate"],
            "avg_api_calls": stats["avg_api_calls"],
            "recommended_approach": None,
            "avoid_approaches": [],
        }

        if successful:
            steps = json.loads(successful["decomposed_steps"]) if isinstance(successful["decomposed_steps"], str) else successful["decomposed_steps"]
            hints["recommended_approach"] = {
                "steps": steps,
                "tools": json.loads(successful["tools_used"]) if isinstance(successful["tools_used"], str) else successful["tools_used"],
                "prior_api_calls": successful["api_calls"],
                "prior_time_ms": successful["execution_time_ms"],
            }

        for f in failed:
            hints["avoid_approaches"].append({
                "steps": json.loads(f["decomposed_steps"]) if isinstance(f["decomposed_steps"], str) else f["decomposed_steps"],
                "error": f["error_context"],
            })

        return hints

    def generate_learning_report(self, instruction_pattern: str = "") -> dict:
        """Generate a report showing measurable improvement over time."""
        stats = self.execution_memory.get_execution_stats(instruction_pattern)
        caps = self.capability_memory.get_all_capabilities()

        synthesized_count = sum(1 for c in caps if c.get("synthesized"))
        total_caps = len(caps)

        report = {
            "execution_stats": stats,
            "capabilities": {
                "total": total_caps,
                "synthesized_at_runtime": synthesized_count,
                "pre_registered": total_caps - synthesized_count,
            },
            "improvement_signals": [],
        }

        if stats["total_runs"] >= 2:
            time_improvement = stats["first_run_time_ms"] - stats["latest_run_time_ms"]
            call_improvement = stats["first_run_api_calls"] - stats["latest_run_api_calls"]

            if time_improvement > 0:
                report["improvement_signals"].append(
                    f"Execution time reduced by {time_improvement}ms "
                    f"({stats['first_run_time_ms']}ms → {stats['latest_run_time_ms']}ms)"
                )
            if call_improvement > 0:
                report["improvement_signals"].append(
                    f"API calls reduced by {call_improvement} "
                    f"({stats['first_run_api_calls']} → {stats['latest_run_api_calls']})"
                )
            if stats["success_rate"] > 0.5:
                report["improvement_signals"].append(
                    f"Success rate: {stats['success_rate']:.0%} over {stats['total_runs']} runs"
                )

        return report

    def suggest_decomposition(self, instruction: str, hints: dict | None) -> str:
        """Use learning to suggest a better decomposition strategy."""
        if not hints or not hints.get("recommended_approach"):
            return ""

        approach = hints["recommended_approach"]
        return (
            f"Based on {hints['total_runs']} prior runs (success rate: {hints['success_rate']:.0%}), "
            f"recommend reusing approach: {json.dumps(approach['steps'])} "
            f"which previously took {approach['prior_api_calls']} API calls "
            f"in {approach['prior_time_ms']}ms."
        )
