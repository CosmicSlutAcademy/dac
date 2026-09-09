"""Tests for dac.site (GCI site generator, no network)."""
import json
import os
import tempfile
import unittest

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-site-")

from dac.site import build, update, ITEMS  # noqa: E402


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp(prefix="gci-site-")

    def test_build_creates_site(self):
        out = build(out_dir=self.out)
        self.assertTrue((out / "index.html").exists())
        self.assertTrue((out / "feed.json").exists())
        feed = json.load(open(out / "feed.json"))
        self.assertEqual(feed["rotation_hours"], 2)
        self.assertEqual(len(feed["items"]), len(ITEMS))
        self.assertGreaterEqual(len(ITEMS), 12)

    def test_index_has_protection_and_rotation_js(self):
        out = build(out_dir=self.out)
        html = (out / "index.html").read_text()
        self.assertIn("Galactic Cyber Intelligence", html)
        self.assertIn("setInterval", html)
        self.assertIn("FEED", html)

    def test_update_rotates_and_persists_state(self):
        out = build(out_dir=self.out)
        update(out_dir=self.out)
        update(out_dir=self.out)
        state = json.load(open(out / "state.json"))
        self.assertEqual(state["index"], 2)
        # index.html regenerated with the new featured item
        html = (out / "index.html").read_text()
        self.assertIn(ITEMS[2]["title"], html)


if __name__ == "__main__":
    unittest.main()
