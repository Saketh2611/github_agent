import json
from datetime import datetime, timezone
from typing import Any
from supabase import Client


class CapabilityMemory:
    def __init__(self, db: Client):
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
        response = self.db.table("capabilities").upsert(record, on_conflict="name").execute()
        return response.data[0] if response.data else record

    def find_capability(self, name: str) -> dict | None:
        response = (
            self.db.table("capabilities")
            .select("*")
            .eq("name", name)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def search_capabilities(self, query: str, limit: int = 5) -> list[dict]:
        response = (
            self.db.table("capabilities")
            .select("*")
            .or_(f"name.ilike.%{query}%,description.ilike.%{query}%")
            .order("success_rate", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def record_usage(self, name: str, success: bool, constraint: str | None = None):
        cap = self.find_capability(name)
        if not cap:
            return

        updates: dict[str, Any] = {"last_used_at": datetime.now(timezone.utc).isoformat()}
        if success:
            updates["success_count"] = cap["success_count"] + 1
        else:
            updates["failure_count"] = cap["failure_count"] + 1

        total = (cap["success_count"] + (1 if success else 0)) + (cap["failure_count"] + (0 if success else 1))
        updates["success_rate"] = round((cap["success_count"] + (1 if success else 0)) / total, 3)

        if constraint:
            existing = json.loads(cap["discovered_constraints"]) if cap["discovered_constraints"] else []
            if constraint not in existing:
                existing.append(constraint)
                updates["discovered_constraints"] = json.dumps(existing)

        self.db.table("capabilities").update(updates).eq("name", name).execute()

    def get_all_capabilities(self) -> list[dict]:
        response = (
            self.db.table("capabilities")
            .select("name, description, http_method, endpoint_template, success_rate, synthesized")
            .order("success_rate", desc=True)
            .execute()
        )
        return response.data or []

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
