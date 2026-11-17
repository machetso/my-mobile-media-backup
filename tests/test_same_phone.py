"""Never the same phone twice in "Known phones" (user request 2026-11-17: a reinstalled phone
app gets a new key and was paired as a second "Pixel 10 Pro")."""

import unittest
from unittest import mock

from phonebackup import companion


def cfg_with(*entries):
    return {"companion_phones": [dict(e) for e in entries]}


OLD = {"phone_id": "old", "name": "Pixel 10 Pro", "paired": "2026-11-17 15:16"}
NEW = {"phone_id": "new", "name": "Pixel 10 Pro", "paired": "2026-11-17 20:15"}
OTHER = {"phone_id": "sam", "name": "SM-G780G", "paired": "2026-11-04 20:55"}


class SamePhoneTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch("phonebackup.companion.config.save")      # never the real settings file
        p.start()
        self.addCleanup(p.stop)

    def test_same_serial_replaced_without_asking(self):
        cfg = cfg_with(dict(OLD, serial="S1"), NEW, OTHER)
        dropped = companion.remember_serial(cfg, dict(NEW), "S1")
        self.assertEqual([p["phone_id"] for p in dropped], ["old"])
        ids = [p["phone_id"] for p in companion.phones(cfg)]
        self.assertEqual(sorted(ids), ["new", "sam"])
        self.assertEqual(companion.paired_for(cfg, "Pixel 10 Pro")["serial"], "S1")

    def test_same_name_without_serial_is_asked(self):
        cfg = cfg_with(OLD, NEW, OTHER)
        sure, maybe = companion.same_phone_pairings(cfg, NEW, "S1")
        self.assertEqual(sure, [])
        self.assertEqual([p["phone_id"] for p in maybe], ["old"])

    def test_two_identical_models_with_other_serials_are_not_mixed(self):
        cfg = cfg_with(dict(OLD, serial="S2"), NEW)
        self.assertEqual(companion.same_phone_pairings(cfg, NEW, "S1"), ([], []))
        self.assertEqual(companion.remember_serial(cfg, dict(NEW), "S1"), [])
        self.assertEqual(len(companion.phones(cfg)), 2)

    def test_different_phone_answer_is_remembered(self):
        cfg = cfg_with(OLD, NEW)
        companion.mark_different(cfg, NEW, OLD)
        self.assertEqual(companion.same_phone_pairings(cfg, NEW), ([], []))

    def test_cable_pairing_stores_the_serial(self):
        import inspect
        src = inspect.getsource(companion.pair_over_cable)
        self.assertIn('"serial": adb_source.serial', src)
        self.assertIn("remember_serial(cfg, entry, adb_source.serial)", src)


if __name__ == "__main__":
    unittest.main()
