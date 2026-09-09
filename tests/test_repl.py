"""Tests for dac.repl direct command execution."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-repl-")

from dac.repl import _maybe_run_direct, _is_action_request, _action_messages, ACTION_WRAP  # noqa: E402


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



class ActionModeTest(unittest.TestCase):
    def test_is_action_request_detects_build_words(self):
        self.assertTrue(_is_action_request("Automate the process"))
        self.assertTrue(_is_action_request("build a landing page"))
        self.assertTrue(_is_action_request("create a script that monitors"))
        self.assertTrue(_is_action_request("set up a telegram bot"))

    def test_is_action_request_false_for_chat(self):
        self.assertFalse(_is_action_request("explain what is happening"))
        self.assertFalse(_is_action_request("hello"))

    def test_action_messages_appends_wrapper(self):
        messages = [{"role": "user", "content": "build me a tool"}]
        out = _action_messages(messages, "build me a tool")
        self.assertEqual(len(out), 1)
        self.assertIn(ACTION_WRAP, out[0]["content"])

    def test_action_messages_untouched_for_explain(self):
        messages = [{"role": "user", "content": "explain phishing"}]
        out = _action_messages(messages, "explain phishing")
        self.assertEqual(out, messages)


if __name__ == "__main__":
    unittest.main()
