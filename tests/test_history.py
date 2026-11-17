"""Backup history (Manage backups → Backup history): backups from the phone and additions from
other sources, remembered in the settings and read back from the reports."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import history  # noqa: E402
from phonebackup.backup import perform_backup  # noqa: E402
from phonebackup.importer import perform_import  # noqa: E402
from phonebackup.sources import FolderSource  # noqa: E402
from tests.test_all import jpeg_with_exif  # noqa: E402

KEY = "Pixel 10 Pro - Sam"


class History(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbhistory_"))
        self.phone, self.old, self.d1 = self.tmp / "phone", self.tmp / "old drive", self.tmp / "hdd1"
        self.d1.mkdir()
        self.cfg = {"fsync": False}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, base, rel, data):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def run_both(self):
        self.put(self.phone, "DCIM/Camera/IMG_A.jpg", jpeg_with_exif("2025:03:15 10:00:00"))
        src = FolderSource(self.phone, device_name="Pixel 10 Pro")
        perform_backup(src, "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d1], self.cfg, interactive=False)
        self.put(self.old, "2019/DSC_0001.JPG", jpeg_with_exif("2019:07:14 12:00:00"))
        self.put(self.old, "2019/DSC_0002.JPG", jpeg_with_exif("2019:07:15 12:00:00"))
        perform_import(self.old, [self.d1 / "Sam" / "Pixel 10 Pro"], self.cfg, interactive=False)

    def test_backup_and_import_are_recorded(self):
        self.run_both()
        rec = self.cfg["backup_history"][KEY]
        self.assertEqual([e["kind"] for e in rec], [history.BACKUP, history.IMPORT])
        self.assertEqual([e["files"] for e in rec], [1, 2])
        self.assertTrue(all(e["status"] == "COMPLETED" for e in rec))
        self.assertIn("Pixel 10 Pro", rec[0]["source"])
        self.assertIn("old drive", rec[1]["source"])
        self.assertEqual(rec[0]["drives"], [str(self.d1)])

    def test_order_and_merge_with_reports(self):
        self.run_both()
        sets = [self.d1 / "Sam" / "Pixel 10 Pro"]
        newest = history.entries(self.cfg, KEY, sets)
        self.assertEqual([e["kind"] for e in newest], [history.IMPORT, history.BACKUP])   # same run listed once
        oldest = history.entries(self.cfg, KEY, sets, newest_first=False)
        self.assertEqual([e["kind"] for e in oldest], [history.BACKUP, history.IMPORT])

    def test_runs_from_reports_only(self):
        """Backups made before this version: the history comes from the reports on the drive."""
        self.run_both()
        found = history.entries({}, KEY, [self.d1 / "Sam" / "Pixel 10 Pro"], newest_first=False)
        self.assertEqual([e["kind"] for e in found], [history.BACKUP, history.IMPORT])
        self.assertEqual([e["files"] for e in found], [1, 2])
        self.assertGreater(found[1]["bytes"], 0)
        self.assertEqual(found[0]["drives"], [str(self.d1)])
        self.assertEqual(found[0]["status"], "COMPLETED")

    def test_numbers_any_language(self):
        self.assertEqual(history._numbers("12 Dateien, 48,3 MB (50,612,345 bytes)"), (12, 50612345))
        self.assertEqual(history._numbers(""), (0, 0))


class Completeness(unittest.TestCase):
    """Complete backups: the drive answered "Yes" is the reference, other drives are compared."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbcomplete_"))
        self.phone = self.tmp / "phone"
        self.a, self.b = self.tmp / "hdd-a", self.tmp / "hdd-b"
        for d in (self.a, self.b):
            d.mkdir()
        self.cfg = {"fsync": False}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def backup(self, drives):
        src = FolderSource(self.phone, device_name="Pixel 10 Pro")
        perform_backup(src, "Pixel 10 Pro", "Sam", ["DCIM/Camera"], drives, self.cfg, interactive=False)

    def test_reference_and_compare(self):
        from phonebackup import completeness
        cam = self.phone / "DCIM/Camera"
        cam.mkdir(parents=True)
        (cam / "IMG_A.jpg").write_bytes(jpeg_with_exif("2025:03:15 10:00:00"))
        self.backup([self.b])                                    # drive B: only the first photo
        (cam / "IMG_B.jpg").write_bytes(jpeg_with_exif("2025:04:15 10:00:00"))
        self.backup([self.a])
        rel, drives = "Sam/Pixel 10 Pro", [str(self.a), str(self.b)]
        self.assertEqual(completeness.check(self.cfg, KEY, rel, drives), {})      # nothing marked yet
        completeness.mark_complete(self.cfg, KEY, [str(self.a)])
        res = completeness.check(self.cfg, KEY, rel, drives)
        self.assertTrue(res[str(self.a)]["complete"])
        self.assertFalse(res[str(self.b)]["complete"])
        self.assertEqual(res[str(self.b)]["missing"], 1)
        self.backup([self.b])                                    # B catches up
        self.assertTrue(completeness.check(self.cfg, KEY, rel, drives)[str(self.b)]["complete"])
        shutil.rmtree(self.b)                                    # B not connected: last result kept
        res = completeness.check(self.cfg, KEY, rel, drives)
        self.assertTrue(res[str(self.b)]["complete"])
        self.assertFalse(res[str(self.b)]["live"])


class Generations(unittest.TestCase):
    def test_summary(self):
        from phonebackup import generations
        from phonebackup.export import Run
        runs = [Run(1, "full", "f", "2026-08-01 10:00:00", "x", "COMPLETED"),
                Run(2, "differential", "d", "2026-09-01 10:00:00", "x", "COMPLETED"),
                Run(3, "incremental", "i", "2026-09-05 10:00:00", None, "RUNNING"),
                Run(4, "incremental", "i2", "2026-09-06 10:00:00", "x", "REMOVED")]
        s = generations.summarize(runs)
        self.assertEqual(s["full"], {"count": 1, "last": "2026-08-01 10:00:00"})
        self.assertEqual(s["differential"]["count"], 1)
        self.assertEqual(s["incremental"]["count"], 0)
        self.assertEqual([u["type"] for u in s["unfinished"]], ["incremental"])

    def test_unfinished_run_stays_visible(self):
        cfg = {}
        history.start(cfg, KEY, history.BACKUP, "2026-11-16T20:00:00", "Pixel 10 Pro", [])
        self.assertEqual(len(history.unfinished(history.entries(cfg, KEY))), 1)
        history.record(cfg, KEY, history.BACKUP, "2026-11-16T20:00:00", "Pixel 10 Pro", 3, 30, "COMPLETED")
        self.assertEqual(history.unfinished(history.entries(cfg, KEY)), [])
        self.assertEqual(len(cfg["backup_history"][KEY]), 1)        # the same run, not a second one


if __name__ == "__main__":
    unittest.main()
