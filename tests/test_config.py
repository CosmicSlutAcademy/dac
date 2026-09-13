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


    def test_corrupt_config_returns_defaults(self):
        """Corrupt config.json should not crash; falls back to defaults."""
        CONFIG_FILE.write_text("not-valid-json!!!", encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cfg = load_config()
        self.assertIn("Warning", buf.getvalue())
        for k, v in DEFAULTS.items():
            if k == "projects_dir":
                self.assertEqual(cfg[k], str(PROJECTS_DIR))
            else:
                self.assertEqual(cfg[k], v)
        # Clean up
        CONFIG_FILE.unlink()

    def test_empty_config_file_returns_defaults(self):
        """Empty config.json should not crash."""
        CONFIG_FILE.write_text("", encoding="utf-8")
        cfg = load_config()
        self.assertEqual(cfg["model"], "gpt-4o")

if __name__ == "__main__":
    unittest.main()


class ConfigBackupTest(unittest.TestCase):
    def setUp(self):
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        backup = CONFIG_DIR / "config.json.bak"
        if backup.exists():
            backup.unlink()
        tmp = CONFIG_DIR / "config.json.tmp"
        if tmp.exists():
            tmp.unlink()

    def tearDown(self):
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        backup = CONFIG_DIR / "config.json.bak"
        if backup.exists():
            backup.unlink()
        tmp = CONFIG_DIR / "config.json.tmp"
        if tmp.exists():
            tmp.unlink()

    def test_save_creates_backup_and_restores_on_corruption(self):
        cfg = load_config()
        save_config(cfg)  # first save: creates config, no prior backup needed
        cfg = load_config()
        cfg["model"] = "gpt-4o-mini"
        cfg["api_key"] = "sk-test-1234"
        save_config(cfg)  # second save: prior config exists -> backup created
        backup = CONFIG_DIR / "config.json.bak"
        self.assertTrue(backup.exists())
        # Corrupt the live config (simulates clipboard/truncation accident).
        CONFIG_FILE.write_text("garbage!!!", encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            restored = load_config()
        self.assertIn("restored from backup", buf.getvalue())
        self.assertEqual(restored["model"], "gpt-4o-mini")
        self.assertEqual(restored["api_key"], "sk-test-1234")
        # The corrupt file should have been replaced with the good config.
        self.assertIn('"gpt-4o-mini"', CONFIG_FILE.read_text(encoding="utf-8"))

    def test_corrupt_with_no_backup_returns_defaults(self):
        CONFIG_FILE.write_text("also-broken", encoding="utf-8")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cfg = load_config()
        self.assertEqual(cfg["model"], "gpt-4o")
        self.assertIn("resetting to defaults", buf.getvalue())

    def test_empty_config_returns_defaults(self):
        CONFIG_FILE.write_text("", encoding="utf-8")
        cfg = load_config()
        self.assertEqual(cfg["model"], "gpt-4o")


if __name__ == "__main__":
    unittest.main()
