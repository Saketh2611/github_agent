import json
from datetime import datetime, timezone
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from DB.models import Capability


class CapabilityMemory:
    def __init__(self, db: Session):
        self.db = db

    def register_capability(
        self,
        name: str,
        description: str,
        http_method: str,
        endpoint_template: str,
        payload_schema: dict | None = None,
        query_params_schema: dict | None = None,
        constraints: list[str] | None = None,
        synthesized: bool = False,
    ) -> dict:
        record = {
            "name": name,
            "description": description,
            "http_method": http_method.upper(),
            "endpoint_template": endpoint_template,
            "payload_schema": json.dumps(payload_schema or {}),
            "query_params_schema": json.dumps(query_params_schema or {}),
            "discovered_constraints": json.dumps(constraints or []),
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0.0,
            "synthesized": synthesized,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used_at": datetime.now(timezone.utc).isoformat(),
        }
        capability = self.db.scalar(
            select(Capability).where(Capability.name == name)
        )
        if capability is None:
            capability = Capability(**record)
            self.db.add(capability)
        else:
            for key, value in record.items():
                setattr(capability, key, value)
        self.db.commit()
        self.db.refresh(capability)
        return capability.to_dict()

    def find_capability(self, name: str) -> dict | None:
        capability = self.db.scalar(
            select(Capability).where(Capability.name == name).limit(1)
        )
        return capability.to_dict() if capability else None

    def search_capabilities(self, query: str, limit: int = 5) -> list[dict]:
        statement = (
            select(Capability)
            .where(
                or_(
                    Capability.name.ilike(f"%{query}%"),
                    Capability.description.ilike(f"%{query}%"),
                )
            )
            .order_by(Capability.success_rate.desc())
            .limit(limit)
        )
        return [cap.to_dict() for cap in self.db.scalars(statement)]

    def record_usage(self, name: str, success: bool, constraint: str | None = None):
        cap = self.db.scalar(select(Capability).where(Capability.name == name))
        if not cap:
            return

        cap.last_used_at = datetime.now(timezone.utc).isoformat()
        if success:
            cap.success_count += 1
        else:
            cap.failure_count += 1

        total = cap.success_count + cap.failure_count
        cap.success_rate = round(cap.success_count / total, 3)

        if constraint:
            existing = (
                json.loads(cap.discovered_constraints)
                if cap.discovered_constraints
                else []
            )
            if constraint not in existing:
                existing.append(constraint)
                cap.discovered_constraints = json.dumps(existing)
        self.db.commit()

    def get_all_capabilities(self) -> list[dict]:
        statement = (
            select(Capability)
            .order_by(Capability.success_rate.desc())
        )
        return [cap.to_summary_dict() for cap in self.db.scalars(statement)]

    def get_capability_summary(self) -> str:
        caps = self.get_all_capabilities()
        if not caps:
            return "No capabilities registered."
        lines = []
        for c in caps:
            synth = " [SYNTHESIZED]" if c.get("synthesized") else ""
            lines.append(
                f"- {c['name']}: {c['description']} "
                f"({c['http_method']} {c['endpoint_template']}, "
                f"success_rate={c['success_rate']:.0%}){synth}"
            )
        return "\n".join(lines)
