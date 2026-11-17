"""Known phone near? (presence.py) – no real network or Bluetooth is used here."""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import presence  # noqa: E402


class Presence(unittest.TestCase):
    def test_ask_proof_matches_phone_app(self):
        # same value in android/.../AskTokenTest.kt
        self.assertEqual(presence.ask_proof("ab" * 32, "pc-1", "0123456789abcdef", 1800000000),
                         "30881616b4c50988c169a867065a8b32")

    def test_bluetooth_names(self):
        paired = [("AA:BB:CC:DD:EE:01", "Sam's Pixel 10 Pro"), ("AA:BB:CC:DD:EE:02", "Jabra Evolve2 65")]
        self.assertEqual(presence.bluetooth_candidates(["Pixel 10 Pro", "Galaxy A55"], paired),
                         {"Pixel 10 Pro": "AA:BB:CC:DD:EE:01"})

    def test_remember_wifi(self):
        cfg = {}
        with mock.patch.object(presence, "mac_of", lambda ip: "aa:bb:cc:dd:ee:ff"), \
                mock.patch.object(presence.config, "save", lambda c: None):
            self.assertTrue(presence.remember_wifi(cfg, "Pixel 10 Pro", "192.0.2.7:41447"))
            self.assertFalse(presence.remember_wifi(cfg, "Pixel 10 Pro", "adb-XYZ._adb-tls-connect._tcp"))
            presence.remember_wifi(cfg, "Pixel 10 Pro", "192.0.2.9")       # new address: replaced
        self.assertEqual(cfg["presence_wifi"], [{"name": "Pixel 10 Pro", "ip": "192.0.2.9",
                                                 "mac": "aa:bb:cc:dd:ee:ff"}])

    def test_scan_combines_ways(self):
        cfg = {"presence_wifi": [{"name": "Pixel 10 Pro", "ip": "192.0.2.9", "mac": "aa:bb:cc:dd:ee:ff"}]}
        entry = {"name": "Pixel 10 Pro", "secret": "ab" * 32, "phone_id": "x"}
        with mock.patch.object(presence, "check_app", lambda c: [(entry, "192.0.2.9:47825", True)]), \
                mock.patch.object(presence, "check_wifi", lambda c: ["Pixel 10 Pro"]), \
                mock.patch.object(presence, "check_bluetooth", lambda names: ["Galaxy A55"]):
            found = presence.scan(cfg)
        self.assertEqual([(f["name"], f["how"], f["ask"], f["auto"]) for f in found],
                         [("Pixel 10 Pro", "app", "192.0.2.9:47825", True), ("Galaxy A55", "bluetooth", None, False)])

    def test_auto_at_most_hourly(self):
        cfg = {}
        with mock.patch.object(presence.config, "save", lambda c: None):
            self.assertTrue(presence.auto_due(cfg, "Pixel 10 Pro", now=10_000))
            presence.auto_started(cfg, "Pixel 10 Pro", now=10_000)
            self.assertFalse(presence.auto_due(cfg, "Pixel 10 Pro", now=10_000 + 3599))
            self.assertTrue(presence.auto_due(cfg, "Pixel 10 Pro", now=10_000 + 3600))

    def test_auto_proof_differs(self):
        a = presence.ask_proof("ab" * 32, "pc-1", "0123456789abcdef", 1800000000, auto=True)
        self.assertEqual(a, "ff3bde18241c2f8ad70ad819c4fe19ef")           # = AskTokenTest.kt


if __name__ == "__main__":
    unittest.main()
