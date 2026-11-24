"""The drives read in the background (user 2026-11-23: the start waited for a sleeping drive) and
"which photos/videos have a checksum on record" (knownhash). Everything in temporary folders."""

import shutil
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import backuplist, completeness, config, drivescan, knownhash  # noqa: E402
from tests.test_reconcile import CFG, REL, Base, media  # noqa: E402
from tests.test_backupid import KEY  # noqa: E402


class Known(Base):
    def test_backup_list_knows_every_photo(self):
        self.backup([self.d1])
        known, unknown = knownhash.known(self.d1 / REL)
        self.assertEqual((len(known), unknown), (4, []))
        self.assertEqual({s for _sha, s in known.values()}, {"list"})

    def test_logs_and_reports_are_not_media(self):
        self.backup([self.d1])
        files = knownhash.media_files(self.d1 / REL)
        self.assertEqual(len(files), 4)
        self.assertFalse(any("Logs" in r or r.endswith((".txt", ".csv", ".html")) for r in files))

    def test_unknown_photo_is_checked_and_remembered(self):
        self.backup([self.d1])
        s = self.d1 / REL
        extra = s / "Karen" / "old" / "IMG_9.jpg"
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"a photo nobody logged")
        known, unknown = knownhash.known(s)
        self.assertEqual(unknown, ["Karen/old/IMG_9.jpg"])
        hashed, errors = knownhash.check(s, unknown)
        self.assertEqual((hashed, errors), (1, []))
        known, unknown = knownhash.known(s)
        self.assertEqual((unknown, known["Karen/old/IMG_9.jpg"][1]), ([], "checked"))
        extra.write_bytes(b"changed afterwards, other size")        # a changed file is not trusted
        self.assertEqual(knownhash.known(s)[1], ["Karen/old/IMG_9.jpg"])

    def test_cancel_keeps_what_was_done(self):
        self.backup([self.d1])
        s = self.d1 / REL
        stop = threading.Event()
        stop.set()
        self.assertEqual(knownhash.check(s, media(s)[:2], cancel=stop), (0, []))


class Scan(Base):
    def test_scan_works_on_a_copy_and_never_saves(self):
        self.backup([self.d1, self.d2])
        cfg = {"backup_profiles": {KEY: {"destinations": [str(self.d1), str(self.d2)]}},
               "phones": {KEY: {"phone": "Pixel 10 Pro", "owner": "Sam",
                                "destinations": [str(self.d1), str(self.d2)]}}}
        saved = []
        real = config.write_private
        config.write_private = lambda path, text: saved.append(path)       # a real write of the settings
        try:
            work, before = drivescan.copy_settings(cfg)
            snap, changes = drivescan.scan_copy(work, before)
        finally:
            config.write_private = real
        self.assertEqual(saved, [])                                   # nothing saved in the thread
        self.assertNotIn("drive_state", cfg)                          # the real settings untouched
        comp = snap["comp"][KEY]
        self.assertEqual({v["files"] for v in comp.values()}, {4})
        self.assertTrue(snap["avail"][str(self.d1)])
        self.assertIn("drive_state", changes)
        self.assertTrue(drivescan.apply_changes(cfg, changes))
        self.assertIn(KEY, cfg["drive_state"])

    def test_a_key_changed_meanwhile_is_not_overwritten(self):
        cfg = {"drive_state": {}}
        work, before = drivescan.copy_settings(cfg)
        work["drive_state"] = {"x": 1}
        changes = {"drive_state": (before["drive_state"], work["drive_state"])}
        cfg["drive_state"] = {"y": 2}                                  # the window changed it
        self.assertFalse(drivescan.apply_changes(cfg, changes))
        self.assertEqual(cfg["drive_state"], {"y": 2})


class ReportsMissing(Base):
    """User 2026-11-23: "Prepare folders" stayed grey – the background scan stopped with an error
    because a backup folder had no report of one kind (history.from_reports)."""

    def test_folder_without_reports_and_all_reports_are_read(self):
        from phonebackup import history
        self.backup([self.d1])
        s = self.d1 / REL
        self.assertEqual(len(history.from_reports([s])), 1)       # one backup report, no import report
        self.photo("IMG_8.jpg", "2025:03:18 10:00:00")
        self.backup([self.d1])                                    # a second report (other start time)
        import time
        time.sleep(0)
        self.assertGreaterEqual(len(history.from_reports([s])), 1)
        empty = self.d2 / "Karen" / "Old phone"
        empty.mkdir(parents=True)
        self.assertEqual(history.from_reports([empty]), [])       # no report at all: no error

    def test_one_bad_backup_does_not_stop_the_scan(self):
        self.backup([self.d1])
        cfg = {"phones": {KEY: {"phone": "Pixel 10 Pro", "owner": "Sam", "destinations": [str(self.d1)]},
                          "Broken - X": {"phone": None, "owner": "X", "destinations": [str(self.d2)]}}}
        work, before = drivescan.copy_settings(cfg)
        snap, _changes = drivescan.scan_copy(work, before)
        self.assertIn(KEY, snap["comp"])
