import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from DB.models import ExecutionLog


class ExecutionMemory:
    def __init__(self, db: Session):
        self.db = db

    def log_execution(
        self,
        instruction: str,
        decomposed_steps: list[dict],
        tools_used: list[str],
        execution_time_ms: int,
        api_calls: int,
        status: str,
        error_context: str | None = None,
        result_summary: str | None = None,
    ) -> dict:
        record = {
            "instruction": instruction,
            "decomposed_steps": json.dumps(decomposed_steps),
            "tools_used": json.dumps(tools_used),
            "execution_time_ms": execution_time_ms,
            "api_calls": api_calls,
            "status": status,
            "error_context": error_context,
            "result_summary": result_summary,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        execution = ExecutionLog(**record)
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution.to_dict()

    def find_similar_executions(self, instruction: str, limit: int = 5) -> list[dict]:
        statement = (
            select(ExecutionLog)
            .where(ExecutionLog.instruction.ilike(f"%{self._extract_keywords(instruction)}%"))
            .order_by(ExecutionLog.executed_at.desc())
            .limit(limit)
        )
        return [row.to_dict() for row in self.db.scalars(statement)]

    def get_execution_stats(self, instruction_pattern: str) -> dict[str, Any]:
        statement = (
            select(
                ExecutionLog.execution_time_ms,
                ExecutionLog.api_calls,
                ExecutionLog.status,
            )
            .where(ExecutionLog.instruction.ilike(f"%{instruction_pattern}%"))
            .order_by(ExecutionLog.executed_at.desc())
            .limit(20)
        )
        rows = self.db.execute(statement).mappings().all()
        if not rows:
            return {"total_runs": 0}

        times = [r["execution_time_ms"] for r in rows]
        calls = [r["api_calls"] for r in rows]
        successes = sum(1 for r in rows if r["status"] == "success")

        return {
            "total_runs": len(rows),
            "avg_time_ms": sum(times) // len(times),
            "avg_api_calls": round(sum(calls) / len(calls), 1),
            "success_rate": round(successes / len(rows), 2),
            "first_run_time_ms": times[-1] if times else 0,
            "latest_run_time_ms": times[0] if times else 0,
            "first_run_api_calls": calls[-1] if calls else 0,
            "latest_run_api_calls": calls[0] if calls else 0,
        }

    def get_failed_approaches(self, instruction: str) -> list[dict]:
        statement = (
            select(
                ExecutionLog.decomposed_steps,
                ExecutionLog.error_context,
                ExecutionLog.tools_used,
            )
            .where(
                ExecutionLog.instruction.ilike(
                    f"%{self._extract_keywords(instruction)}%"
                ),
                ExecutionLog.status == "failed",
            )
            .order_by(ExecutionLog.executed_at.desc())
            .limit(5)
        )
        return [dict(row) for row in self.db.execute(statement).mappings()]

    def get_successful_approach(self, instruction: str) -> dict | None:
        statement = (
            select(
                ExecutionLog.decomposed_steps,
                ExecutionLog.tools_used,
                ExecutionLog.execution_time_ms,
                ExecutionLog.api_calls,
            )
            .where(
                ExecutionLog.instruction.ilike(
                    f"%{self._extract_keywords(instruction)}%"
                ),
                ExecutionLog.status == "success",
            )
            .order_by(ExecutionLog.executed_at.desc())
            .limit(1)
        )
        row = self.db.execute(statement).mappings().first()
        return dict(row) if row else None

    def _extract_keywords(self, instruction: str) -> str:
        stop_words = {"a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
                      "will", "would", "could", "should", "may", "might", "can", "to",
                      "for", "of", "in", "on", "at", "by", "with", "from", "and", "or",
                      "all", "that", "this", "it", "its", "them", "their", "my", "me"}
        words = instruction.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return "%".join(keywords[:4])
