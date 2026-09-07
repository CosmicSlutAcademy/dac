"""Tests for dac.config."""
import os
import tempfile
import unittest
from pathlib import Path

# Isolate from any real user config before importing dac.config.
_HOME = tempfile.mkdtemp(prefix="dac-test-config-")
os.environ["DAC_HOME"] = _HOME

from dac.config import (  # noqa: E402
    load_config,
    save_config,
    ensure_dirs,
    CONFIG_DIR,
    CONFIG_FILE,
    PROJECTS_DIR,
    SESSIONS_DIR,
    TASKS_DIR,
    DEFAULTS,
)


class ConfigTest(unittest.TestCase):
    def test_defaults_and_ensure_dirs(self):
        ensure_dirs()
        for d in (CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR, TASKS_DIR):
            self.assertTrue(d.is_dir())
        cfg = load_config()
        self.assertEqual(cfg["model"], "gpt-4o")
        self.assertEqual(cfg["temperature"], 0.2)
        self.assertFalse(cfg["auto_execute"])

    def test_save_and_load_roundtrip(self):
        cfg = load_config()
        cfg["model"] = "gpt-4o-mini"
        cfg["temperature"] = "0.7"
        save_config(cfg)
        loaded = load_config()
        self.assertEqual(loaded["model"], "gpt-4o-mini")
        self.assertEqual(loaded["temperature"], "0.7")
        self.assertEqual(loaded["api_key"], "")

    def test_api_key_from_env(self):
        os.environ["OPENAI_API_KEY"] = "sk-test-env"
        try:
            cfg = load_config()
            self.assertEqual(cfg["api_key"], "sk-test-env")
        finally:
            del os.environ["OPENAI_API_KEY"]

    def test_no_config_file_returns_defaults(self):
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        cfg = load_config()
        for k, v in DEFAULTS.items():
            if k == "projects_dir":
                self.assertEqual(cfg[k], str(PROJECTS_DIR))
            else:
                self.assertEqual(cfg[k], v)


if __name__ == "__main__":
    unittest.main()
