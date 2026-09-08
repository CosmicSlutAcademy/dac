"""Tests for dac.assistant."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-assistant-")

from dac.assistant import parse_delay, assistant_remind, REMINDER_RE  # noqa: E402


class AssistantTest(unittest.TestCase):
    def test_parse_delay(self):
        self.assertEqual(parse_delay("30s"), 30)
        self.assertEqual(parse_delay("5m"), 300)
        self.assertEqual(parse_delay("2h"), 7200)
        self.assertEqual(parse_delay("10"), 600)  # bare number = minutes

    def test_parse_delay_invalid(self):
        with self.assertRaises(ValueError):
            parse_delay("soon")

    def test_reminder_regex(self):
        m = REMINDER_RE.match("remind drink water in 30m")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "drink water")
        self.assertEqual(m.group(2), "30")
        self.assertEqual(m.group(3), "m")

    def test_assistant_remind_schedules(self):
        from dac import assistant
        with patch.object(assistant, "notify") as n:
            delay = assistant_remind("test reminder", "1s")
            self.assertEqual(delay, 1)
            n.assert_called_once()


if __name__ == "__main__":
    unittest.main()
