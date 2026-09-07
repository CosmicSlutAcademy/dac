"""Tests for dac.core.autonomous."""
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-autonomous-")

from dac.core.autonomous import should_execute, verify_success  # noqa: E402


class AutonomousTest(unittest.TestCase):
    def test_should_execute_true_and_false(self):
        self.assertTrue(should_execute("Do it now\nAUTONOMY_READY"))
        self.assertTrue(should_execute("do it\nautonomy_ready"))
        self.assertFalse(should_execute("Just showing code."))

    def test_verify_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(verify_success({"errors": ["boom"]}))
            self.assertTrue(verify_success({"errors": []}))
            target = os.path.join(tmp, "out.txt")
            self.assertFalse(verify_success({"errors": []}, expected=target))
            open(target, "w").close()
            self.assertTrue(verify_success({"errors": []}, expected=target))


if __name__ == "__main__":
    unittest.main()
