"""Tests for dac.daemon."""
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-daemon-")

from dac.daemon import trigger, daemon_status  # noqa: E402
from dac.config import PID_FILE, TASKS_DIR  # noqa: E402


class DaemonTest(unittest.TestCase):
    def test_trigger_writes_task_and_flag(self):
        name = trigger("do something", task_name="daemon-task")
        self.assertTrue((TASKS_DIR / f"{name}.json").exists())

    def test_daemon_status_missing_pid(self):
        if PID_FILE.exists():
            PID_FILE.unlink()
        running, pid = daemon_status()
        self.assertFalse(running)
        self.assertIsNone(pid)

    def test_daemon_status_alive_pid(self):
        PID_FILE.write_text(str(os.getpid()))
        try:
            running, pid = daemon_status()
            self.assertTrue(running)
            self.assertEqual(pid, os.getpid())
        finally:
            PID_FILE.unlink()

    def test_daemon_status_stale_pid_cleans_up(self):
        PID_FILE.write_text("999999999")
        running, pid = daemon_status()
        self.assertFalse(running)
        self.assertFalse(PID_FILE.exists())


if __name__ == "__main__":
    unittest.main()
