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
    extract_code_blocks_with_lang,
    parse_json,
)


class ParseTest(unittest.TestCase):
    def test_extract_code_blocks(self):
        text = "Here:\n```python\nprint('hi')\n```\nand:\n```bash\nls -la\n```"
        blocks = extract_code_blocks(text)
        self.assertEqual(blocks, ["print('hi')", "ls -la"])

    def test_extract_code_blocks_with_lang(self):
        text = "```python\nprint('hi')\n```\n```bash\necho ok\n```"
        blocks = extract_code_blocks_with_lang(text)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0], ("python", "print('hi')"))
        self.assertEqual(blocks[1], ("bash", "echo ok"))

    def test_extract_code_blocks_with_lang_plain_fence(self):
        blocks = extract_code_blocks_with_lang("```\nwhoami\n```")
        self.assertEqual(blocks, [("bash", "whoami")])

    def test_extract_code_blocks_with_lang_sh_zsh(self):
        text = "```sh\necho hi\n```\n```zsh\nls\n```"
        blocks = extract_code_blocks_with_lang(text)
        self.assertEqual(blocks[0][0], "bash")
        self.assertEqual(blocks[1][0], "bash")

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

class RetryTest(unittest.TestCase):
    def test_retry_after_seconds_from_message(self):
        from dac.core.llm import _retry_after_seconds
        class _Err:
            headers = {}
            def read(self):
                return b'{"error": {"message": "Rate limit reached. Please try again in 6.664s."}}'
        self.assertEqual(_retry_after_seconds(_Err()), 6.664)

    def test_retry_after_seconds_from_header(self):
        from dac.core.llm import _retry_after_seconds
        class _Err:
            headers = {"Retry-After": "3"}
            def read(self):
                return b'{"error": {"message": "rate limited"}}'
        self.assertEqual(_retry_after_seconds(_Err()), 3.0)

    def test_post_json_retries_on_429(self):
        from dac.core.llm import _post_json
        import urllib.error

        calls = {"n": 0}

        def fake_urlopen(req, timeout=120):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
            resp = unittest.mock.MagicMock()
            resp.read.return_value = b'{"ok": true}'
            ctx = unittest.mock.MagicMock()
            ctx.__enter__.return_value = resp
            return ctx

        with unittest.mock.patch("dac.core.llm.time.sleep") as sleep, \
             unittest.mock.patch("dac.core.llm.urllib.request.urlopen", side_effect=fake_urlopen):
            result = _post_json("https://x/v1/chat/completions", {}, {"model": "gpt-4o"})
            self.assertEqual(result, {"ok": True})
            self.assertEqual(calls["n"], 2)
            sleep.assert_called_once()

    def test_post_json_gives_up_after_retries(self):
        from dac.core.llm import _post_json, LLMError
        import urllib.error

        def fake_urlopen(req, timeout=120):
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

        with unittest.mock.patch("dac.core.llm.time.sleep"), \
             unittest.mock.patch("dac.core.llm.urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(LLMError):
                _post_json("https://x/v1/chat/completions", {}, {"model": "gpt-4o"}, max_retries=2)


if __name__ == "__main__":
    unittest.main()

