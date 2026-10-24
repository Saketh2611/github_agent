import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from DB.database import Database
from src.memory.capability_memory import CapabilityMemory
from src.memory.execution_memory import ExecutionMemory


class SQLiteMemoryTests(unittest.TestCase):
    def setUp(self):
        self.database = Database("sqlite://")
        self.session = self.database.create_session()
        self.execution_memory = ExecutionMemory(self.session)
        self.capability_memory = CapabilityMemory(self.session)

    def tearDown(self):
        self.session.close()
        self.database.close()

    def test_execution_memory_queries_and_stats(self):
        self.execution_memory.log_execution(
            instruction="list open issues",
            decomposed_steps=[{"step_number": 1}],
            tools_used=["list_issues"],
            execution_time_ms=120,
            api_calls=2,
            status="success",
        )
        self.execution_memory.log_execution(
            instruction="list closed issues",
            decomposed_steps=[{"step_number": 2}],
            tools_used=["list_issues"],
            execution_time_ms=240,
            api_calls=4,
            status="failed",
            error_context="request failed",
        )

        stats = self.execution_memory.get_execution_stats("issues")
        self.assertEqual(stats["total_runs"], 2)
        self.assertEqual(stats["avg_time_ms"], 180)
        self.assertEqual(stats["avg_api_calls"], 3.0)
        self.assertEqual(stats["success_rate"], 0.5)
        self.assertEqual(len(self.execution_memory.find_similar_executions("issues")), 2)
        other_session = self.database.create_session()
        try:
            other_memory = ExecutionMemory(other_session)
            self.assertEqual(other_memory.get_execution_stats("issues")["total_runs"], 2)
        finally:
            other_session.close()
        self.assertEqual(
            self.execution_memory.get_failed_approaches("closed issues")[0]["error_context"],
            "request failed",
        )
        self.assertIsNotNone(self.execution_memory.get_successful_approach("open issues"))

    def test_file_database_persists_after_reopen(self):
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "agent.sqlite3"
            database_url = f"sqlite:///{database_path.as_posix()}"
            database = Database(database_url)
            session = database.create_session()
            try:
                ExecutionMemory(session).log_execution(
                    instruction="persist this instruction",
                    decomposed_steps=[],
                    tools_used=[],
                    execution_time_ms=10,
                    api_calls=1,
                    status="success",
                )
            finally:
                session.close()
                database.close()

            reopened_database = Database(database_url)
            reopened_session = reopened_database.create_session()
            try:
                stats = ExecutionMemory(reopened_session).get_execution_stats(
                    "persist this instruction"
                )
                self.assertEqual(stats["total_runs"], 1)
            finally:
                reopened_session.close()
                reopened_database.close()

    def test_capability_memory_crud_and_usage(self):
        capability = self.capability_memory.register_capability(
            name="list_issues",
            description="List repository issues",
            http_method="get",
            endpoint_template="/repos/{owner}/{repo}/issues",
            query_params_schema={"state": "open|closed"},
        )
        self.assertEqual(capability["http_method"], "GET")
        self.assertEqual(capability["query_params_schema"], '{"state": "open|closed"}')

        self.capability_memory.record_usage(
            "list_issues", success=True, constraint="requires repo scope"
        )
        self.capability_memory.record_usage("list_issues", success=False)

        stored = self.capability_memory.find_capability("list_issues")
        self.assertEqual(stored["success_count"], 1)
        self.assertEqual(stored["failure_count"], 1)
        self.assertEqual(stored["success_rate"], 0.5)
        self.assertEqual(
            self.capability_memory.search_capabilities("repository")[0]["name"],
            "list_issues",
        )
        self.assertEqual(
            self.capability_memory.get_all_capabilities()[0]["name"], "list_issues"
        )


if __name__ == "__main__":
    unittest.main()
