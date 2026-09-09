"""End-to-end tests for the DAC CLI via subprocess (hermetic DAC_HOME)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_cli(*args, env_extra=None, cwd=REPO):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-m", "dac", *args],
        capture_output=True, text=True, env=env, cwd=cwd, timeout=60,
    )


class CliTest(unittest.TestCase):
    def test_no_args_prints_help(self):
        p = run_cli()
        self.assertEqual(p.returncode, 0)
        self.assertIn("usage:", p.stdout.lower())

    def test_init_sets_api_key_and_model(self):
        with tempfile.TemporaryDirectory() as home:
            p = run_cli("init", "--api-key", "sk-cli-test", "--model", "gpt-4o-mini",
                        env_extra={"DAC_HOME": home})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("DAC initialized", p.stdout)
            cfg = json.load(open(os.path.join(home, "config.json")))
            self.assertEqual(cfg["api_key"], "sk-cli-test")
            self.assertEqual(cfg["model"], "gpt-4o-mini")

    def test_config_show_masks_api_key(self):
        with tempfile.TemporaryDirectory() as home:
            run_cli("init", "--api-key", "sk-super-secret-1234", env_extra={"DAC_HOME": home})
            p = run_cli("config", "--show", env_extra={"DAC_HOME": home})
            self.assertIn("sk-***", p.stdout)
            self.assertNotIn("sk-super-secret-1234", p.stdout)

    def test_run_python(self):
        p = run_cli("run", "print(2 ** 10)")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("1024", p.stdout)

    def test_run_bash(self):
        p = run_cli("run", "echo bash-ok; exit 0", "--language", "bash")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("bash-ok", p.stdout)

    def test_tasks_list_empty(self):
        with tempfile.TemporaryDirectory() as home:
            p = run_cli("tasks", "--list", env_extra={"DAC_HOME": home})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("No tasks", p.stdout)

    def test_project_list_missing_dir_no_crash(self):
        with tempfile.TemporaryDirectory() as home:
            p = run_cli("project", "--list", env_extra={"DAC_HOME": home})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("No projects", p.stdout)

    def test_version_flag(self):
        p = run_cli("--version")
        self.assertEqual(p.returncode, 0)
        self.assertRegex(p.stdout.strip(), r"^dac \d+\.\d+\.\d+$")


    def test_config_set_empty_value_fails(self):
        with tempfile.TemporaryDirectory() as home:
            run_cli("init", "--api-key", "sk-real-key", env_extra={"DAC_HOME": home})
            p = run_cli("config", "--set", "api_key=", env_extra={"DAC_HOME": home})
            self.assertEqual(p.returncode, 1)
            self.assertIn("cannot set empty", p.stdout)
            # Original key should still be intact
            p2 = run_cli("config", "--set", "api_key=", env_extra={"DAC_HOME": home})
            cfg = json.load(open(os.path.join(home, "config.json")))
            self.assertEqual(cfg["api_key"], "sk-real-key")

    def test_corrupt_config_does_not_crash(self):
        with tempfile.TemporaryDirectory() as home:
            config_file = os.path.join(home, "config.json")
            with open(config_file, "w") as f:
                f.write("not-json")
            p = run_cli("config", "--show", env_extra={"DAC_HOME": home})
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("Warning", p.stdout)


if __name__ == "__main__":
    unittest.main()
