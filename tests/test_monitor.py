"""Tests for dac.monitor."""
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ["DAC_HOME"] = tempfile.mkdtemp(prefix="dac-test-monitor-")

from dac.monitor import (  # noqa: E402
    extract_value,
    pct_change,
    add_monitor,
    load_monitors,
    remove_monitor,
    run_monitor,
    MONITORS_FILE,
)


class MonitorTest(unittest.TestCase):
    def setUp(self):
        if MONITORS_FILE.exists():
            MONITORS_FILE.unlink()

    def test_extract_value_paths(self):
        data = {"bitcoin": {"usd": 100.5}, "data": [{"price": 42}]}
        self.assertEqual(extract_value(data, "bitcoin.usd"), 100.5)
        self.assertEqual(extract_value(data, "data[0].price"), 42)

    def test_pct_change(self):
        self.assertEqual(pct_change(None, 10), (None, None))
        d, direction = pct_change(100, 105)
        self.assertEqual(d, 5.0)
        self.assertEqual(direction, "UP")
        d, direction = pct_change(100, 90)
        self.assertEqual(d, 10.0)
        self.assertEqual(direction, "DOWN")

    def test_add_remove_list(self):
        add_monitor("TESTMON", url="https://example.com/x.json", path="price", threshold=3.0)
        monitors = load_monitors()
        self.assertEqual(monitors[0]["name"], "TESTMON")
        self.assertEqual(monitors[0]["threshold"], 3.0)
        self.assertEqual(remove_monitor("TESTMON"), 1)
        self.assertEqual(load_monitors(), [])

    def test_add_preset(self):
        add_monitor("BTC")
        m = load_monitors()[0]
        self.assertIn("coingecko", m["url"])
        self.assertEqual(m["path"], "bitcoin.usd")

    def test_run_monitor_alert_on_threshold(self):
        add_monitor("M", url="http://x/price", path="price", threshold=5.0)
        monitors = load_monitors()
        m = monitors[0]
        with patch("dac.monitor.get_json", side_effect=[{"price": 100.0}, {"price": 110.0}]), \
             patch("dac.monitor.run_cmd") as run_cmd, \
             patch("dac.monitor.alert") as alert:
            changed, row = run_monitor(m)
            self.assertFalse(changed)
            # second run with a 10% move (reset the interval gate)
            m["last_run"] = 0
            changed, row = run_monitor(m)
            self.assertTrue(changed)
            alert.assert_called_once()
        os.unlink(MONITORS_FILE)


if __name__ == "__main__":
    unittest.main()
