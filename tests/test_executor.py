"""Tests for dac.core.executor."""
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-executor-")

from dac.core.executor import (  # noqa: E402
    run_cmd,
    run_script_python,
    run_script_bash,
    execute_block,
    write_file,
)


class ExecutorTest(unittest.TestCase):
    def test_run_cmd_ok(self):
        rc, out, err = run_cmd("echo hello")
        self.assertEqual(rc, 0)
        self.assertIn("hello", out)

    def test_run_cmd_failure(self):
        rc, out, err = run_cmd("exit 3")
        self.assertEqual(rc, 3)

    def test_run_script_python(self):
        rc, out, t = run_script_python("print(6 * 7)")
        self.assertEqual(rc, 0)
        self.assertIn("42", out)
        self.assertGreaterEqual(t, 0)

    def test_run_script_bash(self):
        rc, out, t = run_script_bash("echo $((2 + 2))")
        self.assertEqual(rc, 0)
        self.assertIn("4", out)

    def test_execute_block_python_and_bash(self):
        rc_py, out_py, _ = execute_block("print('py')", lang="python")
        rc_sh, out_sh, _ = execute_block("echo sh", lang="bash")
        self.assertEqual(rc_py, 0)
        self.assertIn("py", out_py)
        self.assertEqual(rc_sh, 0)
        self.assertIn("sh", out_sh)

    def test_write_file_creates_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = write_file(os.path.join(tmp, "a/b/c.txt"), "data")
            self.assertTrue(os.path.exists(p))
            with open(p) as f:
                self.assertEqual(f.read(), "data")


if __name__ == "__main__":
    unittest.main()
