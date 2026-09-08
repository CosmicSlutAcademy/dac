"""Tests for dac.telegram_bot (no network)."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-tg-")

from dac.telegram_bot import handle_update  # noqa: E402


def update(text, chat_id=111):
    return {"message": {"chat": {"id": chat_id}, "text": text}}


class TelegramTest(unittest.TestCase):
    def setUp(self):
        self.cfg = {"api_key": "sk-test", "model": "gpt-4o",
                    "max_tokens": 64, "temperature": 0.0}

    def test_help(self):
        with patch("dac.telegram_bot.send") as send:
            handle_update("tok", update("/help"), self.cfg)
            send.assert_called_once()
            args = send.call_args[0]
            self.assertEqual(args[1], 111)
            self.assertIn("/chat", args[2])

    def test_chat_calls_llm(self):
        from dac.core.llm import complete
        with patch("dac.telegram_bot.complete", return_value=("hello back", {"total_tokens": 5})) as c, \
             patch("dac.telegram_bot.send") as send:
            handle_update("tok", update("/chat hello"), self.cfg)
            c.assert_called_once()
            sent = send.call_args[0][2]
            self.assertIn("hello back", sent)
            self.assertIn("tokens: 5", sent)

    def test_chat_error_handled(self):
        from dac.core.llm import LLMError
        with patch("dac.telegram_bot.complete", side_effect=LLMError("no key")), \
             patch("dac.telegram_bot.send") as send:
            handle_update("tok", update("/chat hi"), {"api_key": ""})
            self.assertIn("Error: no key", send.call_args[0][2])

    def test_tasks(self):
        with patch("dac.telegram_bot.list_tasks", return_value=[]), \
             patch("dac.telegram_bot.send") as send:
            handle_update("tok", update("/tasks"), self.cfg)
            self.assertIn("No tasks", send.call_args[0][2])

    def test_unknown_command(self):
        with patch("dac.telegram_bot.send") as send:
            handle_update("tok", update("gibberish"), self.cfg)
            self.assertIn("Unknown command", send.call_args[0][2])


if __name__ == "__main__":
    unittest.main()
