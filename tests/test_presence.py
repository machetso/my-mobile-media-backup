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

    def test_remember_wifi_per_network(self):
        # Android uses another hardware address in every Wi-Fi (user test 2026-11-24): home + office kept
        cfg = {}
        macs = {"192.0.2.9": "aa:bb:cc:dd:ee:01", "198.51.100.75": "aa:bb:cc:dd:ee:02"}
        with mock.patch.object(presence, "mac_of", lambda ip: macs.get(ip, "aa:bb:cc:dd:ee:%02x" % (int(ip.split(".")[-1]) % 256))), \
                mock.patch.object(presence.config, "save", lambda c: None):
            presence.remember_wifi(cfg, "Pixel 10 Pro", "192.0.2.9:47823")          # home
            presence.remember_wifi(cfg, "Pixel 10 Pro", "198.51.100.75")            # office
            self.assertEqual([e["mac"] for e in cfg["presence_wifi"]], ["aa:bb:cc:dd:ee:02", "aa:bb:cc:dd:ee:01"])
            presence.remember_wifi(cfg, "Pixel 10 Pro", "192.0.2.9")                # home again: first
            self.assertEqual([e["ip"] for e in cfg["presence_wifi"]], ["192.0.2.9", "198.51.100.75"])
            for i in range(10):                                                     # at most 6 per phone
                presence.remember_wifi(cfg, "Pixel 10 Pro", "203.0.113.%d" % (100 + i))
        self.assertEqual(len(cfg["presence_wifi"]), presence.WIFI_PER_PHONE)

    def test_check_wifi_finds_moved_phone(self):
        # same network, new address from DHCP: found by its hardware address in the neighbour table
        cfg = {"presence_wifi": [{"name": "Pixel 10 Pro", "ip": "192.0.2.9", "mac": "aa:bb:cc:dd:ee:01"},
                                 {"name": "Pixel 10 Pro", "ip": "198.51.100.5", "mac": "aa:bb:cc:dd:ee:02"}]}
        poked = []
        with mock.patch.object(presence, "_neighbours", lambda: {"aa:bb:cc:dd:ee:02": ("198.51.100.75", False)}), \
                mock.patch.object(presence, "_poke", poked.append), \
                mock.patch.object(presence.time, "sleep", lambda s: None), \
                mock.patch.object(presence, "_reachable", lambda ip, mac: (ip, mac) == ("198.51.100.75", "aa:bb:cc:dd:ee:02")):
            self.assertEqual(presence.check_wifi(cfg), ["Pixel 10 Pro"])
        self.assertIn("198.51.100.75", poked)
        self.assertEqual(cfg["presence_wifi"][1]["ip"], "198.51.100.5")                # cfg not changed here

    def test_reachable_on_any_interface(self):
        # laptop on cable AND Wi-Fi (user test 2026-11-24): one neighbour line per interface
        out = (b"10.20.31.75 dev eth1 lladdr 02:00:5e:10:20:30 STALE \n"
               b"10.20.31.75 dev wlan0 lladdr 02:00:5e:10:20:30 REACHABLE \n")
        with mock.patch.object(presence.sys, "platform", "linux"), \
                mock.patch.object(presence, "_run", lambda a, timeout=10: mock.Mock(stdout=out)):
            self.assertTrue(presence._reachable("10.20.31.75", "02:00:5e:10:20:30"))
            self.assertFalse(presence._reachable("10.20.31.75", "aa:bb:cc:dd:ee:ff"))
            self.assertEqual(presence.mac_of("10.20.31.75"), "02:00:5e:10:20:30")

    def test_scan_combines_ways(self):
        cfg = {"presence_wifi": [{"name": "Pixel 10 Pro", "ip": "192.0.2.9", "mac": "aa:bb:cc:dd:ee:ff"}]}
        entry = {"name": "Pixel 10 Pro", "secret": "ab" * 32, "phone_id": "x"}
        with mock.patch.object(presence, "check_app", lambda c: [(entry, "192.0.2.9:47825", True, False)]), \
                mock.patch.object(presence, "check_wifi", lambda c: ["Pixel 10 Pro"]), \
                mock.patch.object(presence, "check_bluetooth", lambda names: ["Galaxy A55"]):
            found = presence.scan(cfg)
        self.assertEqual([(f["name"], f["how"], f["ask"], f["auto"], f["self"]) for f in found],
                         [("Pixel 10 Pro", "app", "192.0.2.9:47825", True, False),
                          ("Galaxy A55", "bluetooth", None, False, False)])

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

    def test_new_proof_matches_phone_app(self):
        # "how many photos and videos are new?" – same value in AskTokenTest.kt (NEW_PROOF)
        self.assertEqual(presence.new_proof("ab" * 32, "pc-1", "0123456789abcdef", 1800000000, 1790000000,
                                            ["DCIM/Camera", "Pictures/Screenshots"], "no_drive"),
                         "4ec99f908b3b1e63783a0e9b71026e2c")

    def test_announcement_flags(self):
        """v=2: a = allow without asking, s = also start by itself; v=1 (older app): a meant both."""
        entry = {"name": "Pixel 10 Pro", "secret": "ab" * 32}
        txts = [({"v": "2", "a": "1", "t": "00"}, "192.0.2.9:47825"),
                ({"v": "1", "a": "1", "t": "00"}, "192.0.2.8:47825")]
        for txt, want in ((txts[0], (True, False)), (txts[1], (True, True))):
            with mock.patch.object(presence.companion, "phones", lambda c: [entry]), \
                    mock.patch.object(presence.companion, "discover", lambda service_type: [txt]), \
                    mock.patch.object(presence.companion, "match_token", lambda entries, tokens: entry):
                (_e, _a, allow, by_itself), = presence.check_app({})
            self.assertEqual((allow, by_itself), want)


class SinceTest(unittest.TestCase):
    def test_since_only_after_a_complete_backup(self):
        from phonebackup import lastbackup
        cfg = {}
        with mock.patch.object(lastbackup.config, "save", lambda c: None):
            lastbackup.record(cfg, "Pixel 10 Pro", "Karen", ["DCIM/Camera"], ["/media/Backup Disk"], 3, 10,
                              "COMPLETED", started=1_790_000_000)
            key = next(iter(cfg["phones"]))
            self.assertEqual(lastbackup.since(cfg["phones"][key]), 1_790_000_000)
            lastbackup.record(cfg, "Pixel 10 Pro", "Karen", ["DCIM/Camera"], ["/media/Backup Disk"], 1, 5,
                              "CANCELLED", started=1_790_090_000)
            self.assertEqual(lastbackup.since(cfg["phones"][key]), 1_790_000_000)    # the complete one counts




class KeepSeenTest(unittest.TestCase):
    def test_one_missed_search_keeps_the_phone(self):
        """2026-11-20: the nearby line vanished and came back although the phone did not move."""
        from phonebackup import presence
        seen = {}
        pixel = {"name": "Pixel 10 Pro", "how": "app"}
        self.assertEqual(presence.keep_seen(seen, [pixel], now=1000), [pixel])
        self.assertEqual(presence.keep_seen(seen, [], now=1060), [pixel])       # missed once
        self.assertEqual(presence.keep_seen(seen, [], now=1180), [pixel])       # missed twice
        self.assertEqual(presence.keep_seen(seen, [], now=1000 + presence.KEEP_S + 1), [])   # gone


if __name__ == "__main__":
    unittest.main()
