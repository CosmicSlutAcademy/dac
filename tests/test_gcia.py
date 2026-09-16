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


class ContactLogTest(unittest.TestCase):
    def setUp(self):
        import shutil
        if not shutil.which("openssl"):
            self.skipTest("openssl not available")
        from gcia import contactlog
        self.cl = contactlog
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        self._old = (contactlog.LOGDIR, contactlog.LOG_ENC, contactlog.LOG_KEY, contactlog.LOG_META)
        import pathlib
        contactlog.LOGDIR = pathlib.Path(d)
        contactlog.LOG_ENC = pathlib.Path(d) / "contact-log.enc"
        contactlog.LOG_KEY = pathlib.Path(d) / "contact-log.key"
        contactlog.LOG_META = pathlib.Path(d) / "contact-log.meta"

    def tearDown(self):
        from gcia import contactlog
        contactlog.LOGDIR, contactlog.LOG_ENC, contactlog.LOG_KEY, contactlog.LOG_META = self._old
        self._tmp.cleanup()

    def test_add_list_roundtrip(self):
        e = self.cl.add_entry("mind-layer test", mode="hypnagogic", mood="focused",
                              sleep_h=7.5, stress=3, label="insight", tags=["vision"])
        self.assertTrue(e["id"].startswith("cl_"))
        entries = self.cl.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["content"], "mind-layer test")
        self.assertEqual(entries[0]["mode"], "hypnagogic")

    def test_integrity_detected(self):
        self.cl.add_entry("integrity check")
        self.cl.LOG_ENC.write_bytes(self.cl.LOG_ENC.read_bytes() + b"tamper")
        with self.assertRaises(RuntimeError):
            self.cl.list_entries()

    def test_drop_entry(self):
        e = self.cl.add_entry("remove me")
        self.assertTrue(self.cl.drop_entry(e["id"]))
        self.assertEqual(self.cl.list_entries(), [])

    def test_stats_shape(self):
        self.cl.add_entry("a", stress=8, sleep_h=5)
        self.cl.add_entry("b", stress=4, sleep_h=8)
        s = self.cl.stats()
        self.assertEqual(s["entries"], 2)
        self.assertEqual(s["avg_sleep_h"], 6.5)
        self.assertEqual(s["avg_stress"], 6)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            self.cl.add_entry("")
        with self.assertRaises(ValueError):
            self.cl.add_entry("x", stress=99)


class GuardTest(unittest.TestCase):
    def test_no_data(self):
        from gcia.guard import guard_scan
        from gcia import contactlog
        r = guard_scan()
        # With the real (empty) journal this returns no-data; acceptable shape check.
        self.assertIn(r["status"], ("no-data", "clear", "watch", "alert"))

    def test_distress_detector(self):
        from gcia.guard import _distress_hits
        self.assertIn("suicid", _distress_hits("I feel suicid_ thoughts"))  # prefix match guard
        self.assertEqual(_distress_hits("all calm"), [])

    def test_format_report(self):
        from gcia.guard import format_report
        rep = {"status": "clear", "entries": 0, "findings": []}
        self.assertIn("clear", format_report(rep))


class DeckApiTest(unittest.TestCase):
    def test_get_status(self):
        from gcia.deck import api_dispatch_get
        r = api_dispatch_get("/api/status", {})
        self.assertIn("hostname", r)
        self.assertIn("version", r)

    def test_get_charter(self):
        from gcia.deck import api_dispatch_get
        r = api_dispatch_get("/api/charter", {})
        self.assertTrue(r["text"].startswith("# GCIAu Charter"))

    def test_unknown_route(self):
        from gcia.deck import api_dispatch_get
        self.assertIsNone(api_dispatch_get("/api/nope", {}))

    def test_post_contact_log_bad(self):
        from gcia.deck import api_dispatch_post
        r = api_dispatch_post("/api/alert", {"message": "deck test"})
        self.assertEqual(r, {"ok": True})


class DeckImmunityTest(unittest.TestCase):
    def test_host_allowed_loopback(self):
        from gcia.deck import host_allowed
        self.assertTrue(host_allowed("127.0.0.1:8890", None))
        self.assertTrue(host_allowed("localhost:8890", None))
        self.assertFalse(host_allowed("evil.example", None))
        self.assertTrue(host_allowed("evil.example", "s3cret"))

    def test_rate_ok_budget(self):
        from gcia.deck import rate_ok, _hits
        _hits.clear()
        for _ in range(25):
            self.assertTrue(rate_ok("1.2.3.4", "POST"))
        self.assertFalse(rate_ok("1.2.3.4", "POST"))
        self.assertTrue(rate_ok("9.9.9.9", "POST"))  # other IP unaffected

    def test_immunity_checks(self):
        from gcia.deck import api_dispatch_get
        r = api_dispatch_get("/api/immunity", {})
        names = [c["name"] for c in r["checks"]]
        self.assertIn("contact-log integrity", names)
        self.assertIn("csrf", names)

    def test_storm_key_generation(self):
        import pathlib
        from gcia.deck import api_dispatch_post
        with tempfile.TemporaryDirectory() as d:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = d
            try:
                r = api_dispatch_post("/api/remote/generate-key", {})
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
            self.assertTrue(r["public_key"].startswith("ssh-ed25519"))


class TelegramAlertTest(unittest.TestCase):
    def setUp(self):
        from gcia import notify
        self.nt = notify
        self._tmp = tempfile.TemporaryDirectory()
        import pathlib
        self._old = notify.TG_CONF
        notify.TG_CONF = pathlib.Path(self._tmp.name) / "telegram.json"

    def tearDown(self):
        from gcia import notify
        notify.TG_CONF = self._old
        self._tmp.cleanup()

    def test_unconfigured_returns_false(self):
        self.assertFalse(self.nt.telegram_alert("t", "c"))

    def test_set_and_clear(self):
        p = self.nt.set_telegram("tok123", "chat99")
        self.assertTrue(p.endswith("telegram.json"))
        self.assertEqual(self.nt.telegram_config()["chat_id"], "chat99")
        self.assertTrue(self.nt.clear_telegram())
        self.assertEqual(self.nt.telegram_config(), {})


class ContactLogRotationTest(unittest.TestCase):
    def setUp(self):
        import shutil
        if not shutil.which("openssl"):
            self.skipTest("openssl not available")
        from gcia import contactlog
        self.cl = contactlog
        self._tmp = tempfile.TemporaryDirectory()
        d = self._tmp.name
        import pathlib
        self._old = (contactlog.LOGDIR, contactlog.LOG_ENC, contactlog.LOG_KEY, contactlog.LOG_META)
        contactlog.LOGDIR = pathlib.Path(d)
        contactlog.LOG_ENC = pathlib.Path(d) / "contact-log.enc"
        contactlog.LOG_KEY = pathlib.Path(d) / "contact-log.key"
        contactlog.LOG_META = pathlib.Path(d) / "contact-log.meta"

    def tearDown(self):
        from gcia import contactlog
        contactlog.LOGDIR, contactlog.LOG_ENC, contactlog.LOG_KEY, contactlog.LOG_META = self._old
        self._tmp.cleanup()

    def test_rotate_preserves_entries_backs_up(self):
        self.cl.add_entry("before rotate")
        old_key = self.cl.LOG_KEY.read_text()
        r = self.cl.rotate_key()
        self.assertEqual(r["entries"], 1)
        self.assertTrue(r["backup"])
        self.assertNotEqual(self.cl.LOG_KEY.read_text(), old_key)
        self.assertEqual(self.cl.list_entries()[0]["content"], "before rotate")

    def test_backup_writes_files(self):
        self.cl.add_entry("x")
        pair = self.cl.backup()
        self.assertEqual(len(pair), 3)  # .enc .meta .key
        for p in pair:
            self.assertTrue(os.path.getsize(p) > 0)


class FleetTest(unittest.TestCase):
    def test_roster_shape(self):
        from gcia.fleet import roster
        rs = roster()
        self.assertGreaterEqual(len(rs), 12)
        self.assertTrue(any(r["name"] == "captain-core" for r in rs))
        self.assertTrue(any(r["name"] == "pilot-audit" for r in rs))

    def test_run_audit(self):
        from gcia.fleet import run_role
        r = run_role("pilot-audit")
        self.assertTrue(r["ok"])
        self.assertIn("hostname", r["output"])

    def test_unknown_role(self):
        from gcia.fleet import run_role
        r = run_role("pilot-nope")
        self.assertFalse(r["ok"])
        self.assertIn("unknown role", r["error"])

    def test_missing_args(self):
        from gcia.fleet import run_role
        r = run_role("pilot-scan", args={"host": "127.0.0.1"})  # ports missing
        self.assertFalse(r["ok"])
        self.assertIn("missing required", r["error"])

    def test_captain_has_no_tool(self):
        from gcia.fleet import run_role
        r = run_role("captain-core")
        self.assertTrue(r["ok"])
        self.assertIn("captain", r["output"])

    def test_fallback_dispatch(self):
        from gcia.fleet import _dispatch_fallback
        plan = _dispatch_fallback("protect the network with patrol and code the fix")
        roles = plan["roles"]
        self.assertIn("pilot-audit", roles)
        self.assertIn("pilot-patrol", roles)
        self.assertIn("pilot-code", roles)

    def test_fleet_brief_fallback_path(self):
        from unittest import mock
        import gcia.fleet as fleet
        with mock.patch.object(fleet, "_llm_assign", return_value=None), \
             mock.patch.object(fleet, "_synthesize", return_value="fallback report"):
            b = fleet.fleet_brief("quick audit")
            self.assertTrue(b["mission"].endswith(".md"))
            self.assertTrue(b["report"].startswith("fallback"))


class RegistryTest(unittest.TestCase):
    def test_count_and_shape(self):
        from gcia.registry import count, list_registry
        self.assertEqual(count(), 101)
        es = list_registry()
        self.assertEqual(es[0], {"id": "§MDH-ATA-00", "domain": "Multiverse Origin"})

    def test_get_and_search(self):
        from gcia.registry import get_entry, search, INFINITY
        self.assertEqual(get_entry("54")["domain"], "GCIA Intelligence")
        self.assertEqual(INFINITY, "§MDH-ATA-∞")
        self.assertGreaterEqual(len(search("simulation")), 8)

    def test_deck_registry_endpoint(self):
        from gcia.deck import api_dispatch_get
        r = api_dispatch_get("/api/registry", {"q": ["governance"]})
        ids = [i["id"] for i in r["items"]]
        self.assertIn("§MDH-ATA-53", ids)


class BvhTest(unittest.TestCase):
    def setUp(self):
        from gcia import bvh
        self.bvh = bvh
        self._tmp = tempfile.TemporaryDirectory()
        import pathlib
        self._old = (bvh.BVH_DIR, bvh.BVH_JOURNAL)
        bvh.BVH_DIR = pathlib.Path(self._tmp.name)
        bvh.BVH_JOURNAL = pathlib.Path(self._tmp.name) / "bvh-journal.jsonl"

    def tearDown(self):
        from gcia import bvh
        bvh.BVH_DIR, bvh.BVH_JOURNAL = self._old
        self._tmp.cleanup()

    def test_evaluate_verdicts(self):
        self.assertEqual(self.bvh.evaluate("rm -rf /")["verdict"], "deny")
        self.assertEqual(self.bvh.evaluate("cat ~/.ssh/id_ed25519")["verdict"], "deny")
        self.assertEqual(self.bvh.evaluate("git push origin main")["verdict"], "warn")
        self.assertEqual(self.bvh.evaluate("gcia audit")["verdict"], "allow")

    def test_deny_never_executes(self):
        r = self.bvh.run("rm -rf /")
        self.assertFalse(r["ok"])
        self.assertEqual(r["verdict"], "deny")
        rows = self.bvh.journal()
        self.assertEqual(rows[-1]["event"], "denied")

    def test_warn_requires_approval(self):
        target = os.path.join(self._tmp.name, "bvh-probe.txt")
        r = self.bvh.run(f"touch {target}")
        self.assertEqual(r["verdict"], "require-approval")
        self.assertFalse(os.path.exists(target))

    def test_allow_executes_and_journals(self):
        r = self.bvh.run("echo bvh-ok")
        self.assertTrue(r["ok"])
        self.assertEqual(self.bvh.journal()[-1]["rc"], 0)

    def test_anomaly_detects_denials(self):
        self.bvh.run("rm -rf /")
        a = self.bvh.scan_anomalies()
        self.assertEqual(a["status"], "alert")
        self.assertTrue(any(f["signal"] == "containment-breach-attempt" for f in a["findings"]))

    def test_deck_preview_endpoint(self):
        from gcia.deck import api_dispatch_get
        r = api_dispatch_get("/api/bvh/preview", {"command": ["rm -rf /"]})
        self.assertEqual(r["verdict"], "deny")
        a = api_dispatch_get("/api/bvh/anomaly", {})
        self.assertIn("status", a)
