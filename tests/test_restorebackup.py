"""Restore from the normal backup (user decision 2026-11-23). Everything in temporary folders."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonebackup import restorebackup  # noqa: E402
from phonebackup.backup import perform_backup  # noqa: E402
from phonebackup.sources import FolderSource  # noqa: E402
from tests.test_all import jpeg_with_exif  # noqa: E402

REL = Path("Karen") / "Pixel 10 Pro"


class RestoreFromBackup(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="pbrestore_"))
        self.phone, self.hdd = self.t / "phone", self.t / "hdd"
        self.hdd.mkdir()
        for n, when in enumerate(("2025:03:10 10:00:00", "2025:03:11 10:00:00", "2025:07:01 10:00:00")):
            p = self.phone / "DCIM/Camera" / f"IMG_{n}.jpg"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(jpeg_with_exif(when))
        perform_backup(FolderSource(self.phone, device_name="Pixel 10 Pro"), "Pixel 10 Pro", "Karen",
                       ["DCIM/Camera"], [self.hdd], {"fsync": False}, interactive=False)
        self.set = self.hdd / REL

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def test_folders_listed(self):
        got = [(d, n) for d, n, _b in restorebackup.folders(self.set)]
        self.assertEqual(len(got), 2, got)                       # March and July
        self.assertEqual(sum(n for _d, n in got), 3)

    def test_restore_chosen_month_never_overwrite(self):
        march = [d for d, _n, _b in restorebackup.folders(self.set) if d.endswith(".03")]
        out = self.t / "out"
        status, _p, verdict = restorebackup.restore(self.set, march, out)
        self.assertEqual(status, "COMPLETED", verdict)
        self.assertTrue(verdict.startswith("RESTORE OK - 2 files"), verdict)
        self.assertEqual(len(list(out.rglob("*.jpg"))), 2)
        # again: identical files are skipped, nothing doubled
        status, _p, verdict = restorebackup.restore(self.set, march, out)
        self.assertIn("2 were already there", verdict)
        self.assertEqual(len(list(out.rglob("*.jpg"))), 2)
        # another file with the same name: kept, the restored one gets _1
        one = sorted(out.rglob("*.jpg"))[0]
        one.write_bytes(b"other content")
        restorebackup.restore(self.set, march, out)
        self.assertEqual(one.read_bytes(), b"other content")
        self.assertTrue(one.with_name(one.stem + "_1.jpg").is_file())

    def test_phone_layout(self):
        all_dirs = [d for d, _n, _b in restorebackup.folders(self.set)]
        out = self.t / "back"
        status, _p, _v = restorebackup.restore(self.set, all_dirs, out, phone_layout=True)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(sorted(p.name for p in (out / "DCIM/Camera").iterdir()),
                         ["IMG_0.jpg", "IMG_1.jpg", "IMG_2.jpg"])


if __name__ == "__main__":
    unittest.main()
