"""Tests for dac.demo (self-contained, no LLM)."""
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-demo-")

from dac.demo import run_demo  # noqa: E402


class DemoTest(unittest.TestCase):
    def test_run_demo_creates_and_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = run_demo(project_dir=tmp)
            self.assertEqual(rc, 0)
            proj = os.path.join(tmp, "demo")
            self.assertTrue(os.path.exists(os.path.join(proj, "fib.py")))
            self.assertTrue(os.path.exists(os.path.join(proj, "test_fib.py")))


if __name__ == "__main__":
    unittest.main()
