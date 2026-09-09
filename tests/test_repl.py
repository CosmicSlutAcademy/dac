"""Tests for dac.repl direct command execution."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-repl-")

from dac.repl import _maybe_run_direct  # noqa: E402


class ReplDirectTest(unittest.TestCase):
    def test_returns_false_for_normal_prompt(self):
        self.assertFalse(_maybe_run_direct("create a script"))

    def test_runs_dac_command(self):
        with patch("dac.repl.run_cmd", return_value=(0, "api_key: ok\n", "")) as run:
            handled = _maybe_run_direct("dac config --show")
            self.assertTrue(handled)
            run.assert_called_once_with("dac config --show")

    def test_runs_shell_command_with_bang(self):
        with patch("dac.repl.run_cmd", return_value=(0, "hello\n", "")) as run:
            handled = _maybe_run_direct("!echo hello")
            self.assertTrue(handled)
            run.assert_called_once_with("echo hello")

    def test_reports_nonzero_exit(self):
        with patch("dac.repl.run_cmd", return_value=(2, "", "boom")) as run:
            handled = _maybe_run_direct("!false")
            self.assertTrue(handled)
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
