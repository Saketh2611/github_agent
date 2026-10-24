from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExecutionLog(Base):
    __tablename__ = "execution_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'partial_success', 'failed')",
            name="check_execution_log_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    decomposed_steps: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    tools_used: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    execution_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_context: Mapped[str | None] = mapped_column(Text)
    result_summary: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[str] = mapped_column(String, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "decomposed_steps": self.decomposed_steps,
            "tools_used": self.tools_used,
            "execution_time_ms": self.execution_time_ms,
            "api_calls": self.api_calls,
            "status": self.status,
            "error_context": self.error_context,
            "result_summary": self.result_summary,
            "executed_at": self.executed_at,
        }


class Capability(Base):
    __tablename__ = "capabilities"
    __table_args__ = (
        CheckConstraint(
            "http_method IN ('GET', 'POST', 'PATCH', 'PUT', 'DELETE')",
            name="check_capability_http_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    http_method: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_template: Mapped[str] = mapped_column(Text, nullable=False)
    payload_schema: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    query_params_schema: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    discovered_constraints: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    synthesized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    last_used_at: Mapped[str] = mapped_column(String, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "http_method": self.http_method,
            "endpoint_template": self.endpoint_template,
            "payload_schema": self.payload_schema,
            "query_params_schema": self.query_params_schema,
            "discovered_constraints": self.discovered_constraints,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "synthesized": self.synthesized,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
        }

    def to_summary_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "http_method": self.http_method,
            "endpoint_template": self.endpoint_template,
            "success_rate": self.success_rate,
            "synthesized": self.synthesized,
        }
