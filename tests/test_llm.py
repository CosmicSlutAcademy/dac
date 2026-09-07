"""Tests for dac.core.llm parsing and completion plumbing."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-llm-")

from dac.core.llm import (  # noqa: E402
    complete,
    LLMError,
    extract_code_blocks,
    parse_json,
)


class ParseTest(unittest.TestCase):
    def test_extract_code_blocks(self):
        text = "Here:\n```python\nprint('hi')\n```\nand:\n```bash\nls -la\n```"
        blocks = extract_code_blocks(text)
        self.assertEqual(blocks, ["print('hi')", "ls -la"])

    def test_extract_code_blocks_plain_fence(self):
        self.assertEqual(extract_code_blocks("```\nwhoami\n```"), ["whoami"])

    def test_parse_json_plain(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_parse_json_markdown_fence(self):
        text = "```json\n{\"steps\": [\"one\"]}\n```"
        self.assertEqual(parse_json(text), {"steps": ["one"]})

    def test_parse_json_with_surrounding_text(self):
        text = 'Result:\nHere is the plan: {"files": [], "commands": ["echo ok"]}\nDone.'
        self.assertEqual(parse_json(text), {"files": [], "commands": ["echo ok"]})

    def test_parse_json_invalid_raises(self):
        with self.assertRaises(LLMError):
            parse_json("not json at all")


class CompleteTest(unittest.TestCase):
    def test_missing_api_key_raises(self):
        cfg = {"api_key": "", "provider": "openai", "model": "gpt-4o"}
        with self.assertRaises(LLMError):
            complete(cfg, [{"role": "user", "content": "hi"}])

    def test_openai_complete_parses_response(self):
        cfg = {"api_key": "sk-test", "provider": "openai", "model": "gpt-4o",
               "max_tokens": 100, "temperature": 0.0}
        fake = {"choices": [{"message": {"content": "hello"}}], "usage": {"total_tokens": 7}}
        with patch("dac.core.llm._chat_completion", return_value=("hello", fake["usage"])) as m:
            text, usage = complete(cfg, [{"role": "user", "content": "say hi"}])
            self.assertEqual(text, "hello")
            self.assertEqual(usage["total_tokens"], 7)
            m.assert_called_once()


if __name__ == "__main__":
    unittest.main()
