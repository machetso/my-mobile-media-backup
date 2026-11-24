"""Before the backup: how many files are new, how long (user request 2026-11-22). Temp folders only."""

import os
import shutil
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import precheck  # noqa: E402
from phonebackup.backup import perform_backup  # noqa: E402
from phonebackup.sources import FolderSource  # noqa: E402
from tests.test_all import jpeg_with_exif  # noqa: E402

CFG = {"fsync": False}
REL = "Sam/Pixel 10 Pro"


class PrecheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbprecheck_"))
        self.phone, self.d1, self.d2 = self.tmp / "phone", self.tmp / "hdd1", self.tmp / "hdd2"
        for d in (self.d1, self.d2):
            d.mkdir()
        for n in range(3):
            self.photo(f"IMG_{n}.jpg", f"2025:03:1{n} 10:00:00")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def photo(self, name, when):
        p = self.phone / "DCIM/Camera" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(jpeg_with_exif(when))

    def src(self):
        return FolderSource(self.phone, device_name="Pixel 10 Pro")

    def test_counts_new_files_and_writes_nothing(self):
        perform_backup(self.src(), "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d1], CFG, interactive=False)
        self.photo("IMG_9.jpg", "2025:04:01 10:00:00")
        before = sorted(str(p) for p in self.tmp.rglob("*"))
        res = precheck.run(self.src(), ["DCIM/Camera"], [self.d1, self.d2], REL, CFG)
        self.assertEqual(sorted(str(p) for p in self.tmp.rglob("*")), before)    # read only
        self.assertTrue(res.complete)
        self.assertEqual((res.found, res.already, res.new), (4, 0, 1))
        self.assertEqual(res.from_drive, 3)                 # drive 2 gets them from drive 1
        self.assertGreater(res.estimate_seconds(10.0), 0)

    def test_listing_is_reused_by_the_backup(self):
        res = precheck.run(self.src(), ["DCIM/Camera"], [self.d1], REL, CFG)
        self.assertEqual(res.new, 3)
        src = self.src()
        src.list_files = lambda folders: self.fail("the phone was asked again")
        status, _p, results, _v = perform_backup(src, "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d1], CFG,
                                                 interactive=False, listing=res.listing)
        self.assertEqual((status, len(results)), ("COMPLETED", 3))

    def test_skip_returns_what_is_known(self):
        res = precheck.run(self.src(), ["DCIM/Camera"], [self.d1], REL, CFG, stop=lambda: True)
        self.assertFalse(res.complete)
        self.assertEqual(len(res.listing[0]), 3)

    def test_same_name_and_size_outside_the_list_is_maybe_there(self):
        perform_backup(self.src(), "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d1], CFG, interactive=False)
        shutil.copytree(self.d1 / REL, self.d2 / REL)
        shutil.rmtree(self.d2 / REL / ".phonebackup")
        res = precheck.run(self.src(), ["DCIM/Camera"], [self.d2], REL, CFG)
        self.assertEqual((res.new, res.maybe_there), (0, 3))


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None, "PySide6 not installed")
class DialogSmoke(unittest.TestCase):
    def test_dialog_text(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from phonebackup.gui_precheck import describe
        r = precheck.Precheck(found=10, already=7, new=3, new_bytes=300_000_000, complete=True)
        text = describe(r, 25.0, "adb_usb")
        self.assertIn("3 new photos/videos to back up", text)
        self.assertIn("USB cable – USB debugging", text)
        self.assertIn("7 of them already backed up", text)


if __name__ == "__main__":
    unittest.main()
