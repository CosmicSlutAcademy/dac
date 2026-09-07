"""Tests for dac.orchestrator (task lifecycle, no network)."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-orch-")

from dac.orchestrator import (  # noqa: E402
    create_task,
    list_tasks,
    TASKS_DIR,
)



class OrchestratorTest(unittest.TestCase):
    def test_create_and_list_task(self):
        task = create_task("write a test file", task_name="test-task")
        self.assertEqual(task["status"], "pending")
        self.assertTrue((TASKS_DIR / "test-task.json").exists())
        names = [t["name"] for t in list_tasks()]
        self.assertIn("test-task", names)

    def test_execute_task_runs_plan(self):
        from dac.orchestrator import execute_task
        create_task("make a file", task_name="exec-task")
        plan = json.dumps({
            "steps": ["write file"],
            "files": [{"path": "hello.txt", "content": "hi"}],
            "commands": ["cat hello.txt"],
            "summary": "done",
        })
        with tempfile.TemporaryDirectory() as proj, \
             patch("dac.orchestrator.complete", return_value=(plan, {})):
            result = execute_task("exec-task", cfg={"api_key": "sk-x"}, project_dir=proj)
            self.assertEqual(result["status"], "done")
            self.assertTrue(os.path.exists(os.path.join(proj, "hello.txt")))
            self.assertEqual(result["results"]["commands_run"][0]["rc"], 0)
            self.assertIn("hi", result["results"]["commands_run"][0]["output"])

    def test_execute_task_handles_llm_error(self):
        from dac.orchestrator import execute_task
        from dac.core.llm import LLMError
        create_task("broken", task_name="err-task")
        with patch("dac.orchestrator.complete", side_effect=LLMError("no key")):
            result = execute_task("err-task", cfg={"api_key": ""}, project_dir="/tmp/nope")
            self.assertEqual(result["status"], "failed")
            self.assertIn("no key", result.get("error", ""))


if __name__ == "__main__":
    unittest.main()
