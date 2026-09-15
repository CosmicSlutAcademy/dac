"""Tests for GCIA investigation/regulatory CLI modules."""

import os
import tempfile
import unittest

from gcia import policy
from gcia.vault import generate_key, checksum


class PolicyTest(unittest.TestCase):
    def test_briefing_has_guidance(self):
        b = policy.briefing("device")
        self.assertEqual(b["agency"], "GCIAu — Global Cyber Intelligence Authority")
        self.assertTrue(len(b["guidance"]) > 20)
        self.assertIn("generated", b)

    def test_briefing_unknown_theme_falls_back(self):
        b = policy.briefing("nope")
        self.assertIn("Endpoint hardening", b["guidance"])

    def test_checklist_counts(self):
        c = policy.checklist()
        self.assertEqual(c["count"], 5)
        self.assertEqual(c["checklist"][0]["status"], "pending")

    def test_export_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b.json")
            policy.export_json(policy.briefing("data"), p)
            with open(p) as f:
                self.assertIn("data sovereignty", f.read().lower())


class VaultTest(unittest.TestCase):
    def test_keygen_and_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            k = os.path.join(d, "vault.key")
            generate_key(k)
            with open(k) as f:
                key = f.read().strip()
            self.assertEqual(len(key), 64)  # 32 bytes hex
            mode = os.stat(k).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_checksum_stable(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.txt")
            with open(p, "w") as f:
                f.write("gcia test")
            self.assertEqual(len(checksum(p)), 64)


class ReconImportTest(unittest.TestCase):
    def test_local_ips_shape(self):
        from gcia.recon import local_ips
        ips = local_ips()
        self.assertIsInstance(ips, list)


if __name__ == "__main__":
    unittest.main()
