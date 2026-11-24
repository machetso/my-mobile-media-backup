"""Refused backup destinations (UI test 2026-11-23, user decision: block with the reason)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonebackup import destcheck  # noqa: E402


class DestCheckTest(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="destcheck_"))
        self.a, self.b, self.phone = self.t / "DriveA", self.t / "DriveB", self.t / "phone"
        for p in (self.a, self.b, self.phone / "DCIM"):
            p.mkdir(parents=True)
        self.roots = [str(self.a), str(self.b)]
        self.backup = self.a / "PhoneBackups" / "Karen" / "Pixel 10 Pro"
        (self.backup / ".phonebackup").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def why(self, path, others=()):
        return destcheck.problem(str(path), [str(o) for o in others], self.roots, [str(self.phone)])

    def test_normal_drives_are_fine(self):
        self.assertEqual(self.why(self.a / "PhoneBackups"), "")
        self.assertEqual(self.why(self.b / "PhoneBackups", [self.a / "PhoneBackups"]), "")

    def test_the_phone_is_refused(self):
        self.assertIn("on the phone", self.why(self.phone))
        self.assertIn("on the phone", self.why(self.phone / "Backups"))
        self.assertIn("on the phone", self.why("/run/user/1000/gvfs/mtp:host=Google_Pixel/Internal shared storage"))

    def test_inside_a_backup_is_refused(self):
        self.assertIn("inside an existing backup", self.why(self.backup / "2026"))
        self.assertIn("inside an existing backup", self.why(self.backup))

    def test_same_drive_twice_is_refused(self):
        self.assertIn("same drive", self.why(self.a / "Other", [self.a / "PhoneBackups"]))
        self.assertIn("same drive", self.why(self.a, [self.a / "PhoneBackups"]))
        self.assertEqual(self.why(self.a / "PhoneBackups", [self.a / "PhoneBackups"]), "")   # the same entry
        self.assertEqual(self.why(self.a / "X", ["gdrive:"]), "")


if __name__ == "__main__":
    unittest.main()
