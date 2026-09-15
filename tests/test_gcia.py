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


class PatrolTest(unittest.TestCase):
    def test_flag_rows(self):
        from gcia.patrol import _flag_rows
        rows = _flag_rows({"listening_ports": [22, 8080],
                           "world_writable_home": [("x", "0o777")],
                           "pending_updates": 3})
        self.assertTrue(any("22" in r for r in rows))
        self.assertTrue(any("pending" in r for r in rows))

    def test_flag_rows_clean(self):
        from gcia.patrol import _flag_rows
        rows = _flag_rows({"listening_ports": [], "world_writable_home": [], "pending_updates": 0})
        self.assertEqual(rows, [])

    def test_one_patrol_shapes(self):
        from gcia.patrol import one_patrol
        audit, flags = one_patrol(notify_even_clean=True)
        self.assertIn("hostname", audit)


class NotifyTest(unittest.TestCase):
    def test_notify_returns_bool(self):
        from gcia.notify import notify
        # Returns a bool and never raises whether or not termux API exists.
        ok = notify("test", "hello")
        self.assertIsInstance(ok, bool)


class RemoteTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = self._tmp.name
        from gcia import remote
        self.remote = remote
        self._old_peers = remote.PEERS_FILE
        self._old_auth = remote.AUTH_KEYS
        remote.PEERS_FILE = self.remote.PEERS_FILE = __import__("pathlib").Path(self._tmp.name) / "peers.json"
        remote.AUTH_KEYS = self.remote.AUTH_KEYS = __import__("pathlib").Path(self._tmp.name) / "authorized_keys"

    def tearDown(self):
        from gcia import remote
        remote.PEERS_FILE = self._old_peers
        remote.AUTH_KEYS = self._old_auth
        if self._old_home:
            os.environ["HOME"] = self._old_home
        self._tmp.cleanup()

    def test_grant_revoke_roundtrip(self):
        import subprocess, tempfile, pathlib
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGrantKey test@laptop"
        with tempfile.TemporaryDirectory() as d:
            kp = pathlib.Path(d) / "peer.pub"
            kp.write_text(key)
            info = self.remote.grant("laptop", str(kp))
            self.assertIn("audit", info["allowed"])
            peers = self.remote.peers()
            self.assertIn("laptop", peers)
            # authorized_keys line must be force-commanded
            auth = self.remote.AUTH_KEYS.read_text()
            self.assertIn('command="/usr/local/bin/gcia-agent"', auth)
            self.assertIn("no-port-forwarding", auth)
            self.assertTrue(self.remote.revoke("laptop"))
            self.assertNotIn("laptop", self.remote.peers())

    def test_grant_rejects_bad_key(self):
        import pathlib, tempfile
        with tempfile.TemporaryDirectory() as d:
            kp = pathlib.Path(d) / "bad.pub"
            kp.write_text("not a key")
            with self.assertRaises(ValueError):
                self.remote.grant("x", str(kp))


class AgentTest(unittest.TestCase):
    def test_allowlist_denies_unknown(self):
        from gcia.agent import handle
        rc = handle(["rm", "-rf", "/"])
        self.assertEqual(rc, 403)

    def test_allowlist_denies_suspicious_scan_target(self):
        from gcia.agent import handle
        rc = handle(["scan", "evil;rm"])
        self.assertEqual(rc, 403)

    def test_allowlist_allows_audit(self):
        from gcia.agent import handle
        rc = handle(["audit"])
        self.assertEqual(rc, 0)
