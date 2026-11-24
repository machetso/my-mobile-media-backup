"""Imported folders with other files and own file names keep their structure (user rule
2026-11-23) – at import time and as a repair. Temporary folders only."""

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import regroup  # noqa: E402
from phonebackup.importer import CAMERA, OTHER, scan_folder  # noqa: E402
from phonebackup.index import BackupIndex  # noqa: E402


class Rule(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbregroup_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put(self, rel, data=b"x"):
        p = self.tmp / "src" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def test_mixed_folder_keeps_structure_camera_folder_is_sorted(self):
        self.put("pixel10pro -dateien/Documents/CV.pdf")
        self.put("pixel10pro -dateien/Pictures/PokemonGO/Pokemon1.jpg")
        self.put("pixel10pro -dateien/Pictures/PokemonGO/Pokemon2.jpg")
        self.put("pixel10pro -dateien/Pictures/PXL_20260101_101010101.jpg")
        self.put("pixel10pro 27.06.2026/PXL_20260507_200512670.jpg")
        self.put("pixel10pro 27.06.2026/PXL_20260509_104234151.mp4")
        for into_existing in (False, True):
            kinds = {i.rel: i.kind for i in scan_folder(self.tmp / "src", into_existing=into_existing)}
            self.assertEqual(kinds["pixel10pro -dateien/Pictures/PokemonGO"], OTHER)
            self.assertEqual(kinds["pixel10pro -dateien/Pictures"], OTHER)        # even its camera name
            self.assertEqual(kinds["pixel10pro -dateien/Documents"], OTHER)
            self.assertEqual(kinds["pixel10pro 27.06.2026"], CAMERA)


class Repair(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbregroup_"))
        self.s = self.tmp / "MMMB_Vol.1" / "Karen" / "Pixel 10 Pro"
        origin = "C:/Users/Karen/Temp/Google Pixel"
        files = {   # rel in the backup: source path
            "pixel10pro -dateien/Documents/CV.pdf": f"{origin}/pixel10pro -dateien/Documents/CV.pdf",
            "pixel10pro -dateien/Download/Rechnung.pdf": f"{origin}/pixel10pro -dateien/Download/Rechnung.pdf",
            "2025/25.03/Pokemon1.jpg": f"{origin}/pixel10pro -dateien/Pictures/PokemonGO/Pokemon1.jpg",
            "2006/06.06/020_17~2.JPG": f"{origin}/pixel10pro -dateien/Pictures/020_17~2.JPG",
            "2026/26.05/PXL_20260507_200512670.jpg": f"{origin}/pixel10pro 27.06.2026/PXL_20260507_200512670.jpg",
        }
        idx = BackupIndex(self.s)
        for i, (rel, src) in enumerate(files.items()):
            p = self.s / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(bytes([i]) * 10)
            idx.add("import:" + src, 10, 0, f"{i:064x}", rel, "other", "", "")
        idx.commit()
        idx.close()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rels(self):
        db = sqlite3.connect(str(self.s / ".phonebackup" / "index.sqlite"))
        try:
            return sorted(r for (r,) in db.execute("SELECT rel_path FROM files"))
        finally:
            db.close()

    def test_plan_apply_undo(self):
        before = self.rels()
        folders = regroup.plan(self.s)
        self.assertEqual([f.name for f in folders], ["pixel10pro -dateien"])
        self.assertEqual(sorted(w for _r, w in folders[0].moves),
                         ["pixel10pro -dateien/Pictures/020_17~2.JPG",
                          "pixel10pro -dateien/Pictures/PokemonGO/Pokemon1.jpg"])
        moved, skipped, man = regroup.apply(self.s, folders)
        self.assertEqual((moved, skipped), (2, []))
        self.assertTrue((self.s / "pixel10pro -dateien/Pictures/PokemonGO/Pokemon1.jpg").is_file())
        self.assertFalse((self.s / "2006").exists())                         # emptied folder removed
        self.assertTrue((self.s / "2026/26.05/PXL_20260507_200512670.jpg").is_file())   # camera stays
        self.assertIn("pixel10pro -dateien/Pictures/PokemonGO/Pokemon1.jpg", self.rels())
        self.assertEqual(regroup.plan(self.s), [])                           # nothing left to do
        back, sk = regroup.undo(man)
        self.assertEqual((back, sk), (2, []))
        self.assertEqual(self.rels(), before)
        self.assertTrue((self.s / "2006/06.06/020_17~2.JPG").is_file())


class StrayPart(Repair):
    """User 2026-11-23: a second "pixel10pro -dateien" inside the year folder 2026."""

    def test_part_inside_a_year_folder_is_merged(self):
        stray = self.s / "2026" / "pixel10pro -dateien"
        (stray / "Documents" / "Bkp_Signal").mkdir(parents=True)
        (stray / "Documents" / "Bkp_Signal" / "signal.backup").write_bytes(b"signal")
        (stray / "Documents" / "CV.pdf").write_bytes((self.s / "pixel10pro -dateien/Documents/CV.pdf").read_bytes())
        folders = regroup.plan(self.s)
        self.assertEqual(folders[0].strays, 2)
        moved, skipped, man = regroup.apply(self.s, folders)
        self.assertEqual((moved, skipped), (4, []))
        self.assertTrue((self.s / "pixel10pro -dateien/Documents/Bkp_Signal/signal.backup").is_file())
        self.assertFalse(stray.exists())                                   # only ONE folder of that name
        self.assertFalse((self.s / "pixel10pro -dateien/Documents/CV_1.pdf").exists())   # identical: no _1
        reviews = list(self.s.parent.glob("Duplicates */Pixel 10 Pro/2026/pixel10pro -dateien/Documents/CV.pdf"))
        self.assertEqual(len(reviews), 1)
        back, sk = regroup.undo(man)
        self.assertEqual((back, sk), (4, []))
        self.assertTrue((stray / "Documents" / "CV.pdf").is_file())
        self.assertIn("pixel10pro -dateien/Documents/CV.pdf", self.rels())  # the kept file's entry untouched
