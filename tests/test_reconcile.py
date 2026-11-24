"""Backup folders that are not completely known, backup drives added later, choosing the backup
folder by hand (user request 2026-11-22). Everything in temporary folders."""

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import findbackup, reconcile  # noqa: E402
from phonebackup.backup import perform_backup  # noqa: E402
from phonebackup.sources import FolderSource  # noqa: E402
from tests.test_all import jpeg_with_exif  # noqa: E402

CFG = {"fsync": False}
REL = Path("Sam") / "Pixel 10 Pro"


def rows(set_dir):
    db = sqlite3.connect(str(set_dir / ".phonebackup" / "index.sqlite"))
    try:
        return db.execute("SELECT source_path, rel_path, sha256 FROM files").fetchall()
    finally:
        db.close()


def media(set_dir):
    return sorted(p.relative_to(set_dir).as_posix() for p in set_dir.rglob("*")
                  if p.is_file() and not {".phonebackup", "Logs"} & set(p.relative_to(set_dir).parts))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbreconcile_"))
        self.phone = self.tmp / "phone"
        self.d1, self.d2 = self.tmp / "hdd1", self.tmp / "hdd2"
        self.d1.mkdir()
        self.d2.mkdir()
        for n in range(4):
            self.photo(f"IMG_{n}.jpg", f"2025:03:1{n} 10:00:00")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def photo(self, name, when, extra=b""):
        p = self.phone / "DCIM/Camera" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(jpeg_with_exif(when, extra))
        return p

    def source(self, hashes=False):
        s = FolderSource(self.phone, device_name="Pixel 10 Pro", verify_source=hashes)
        s.kind = "USB cable (ADB)"
        return s

    def backup(self, dests, hashes=False, source=None):
        return perform_backup(source or self.source(hashes), "Pixel 10 Pro", "Sam", ["DCIM/Camera"],
                              dests, CFG, interactive=False)


class NotCompletelyKnown(Base):
    def _copy_without_index(self, keep_logs=True):
        self.backup([self.d1])
        shutil.copytree(self.d1 / REL, self.d2 / REL)
        shutil.rmtree(self.d2 / REL / ".phonebackup")
        if not keep_logs:
            shutil.rmtree(self.d2 / REL / "Logs")

    def test_folder_copied_by_hand_is_recognised_by_name_size_and_phone_hash(self):
        self._copy_without_index(keep_logs=False)
        status, _p, results, _v = self.backup([self.d2], hashes=True)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(results, [])                       # nothing copied again
        self.assertEqual(len(rows(self.d2 / REL)), 4)
        self.assertEqual(media(self.d2 / REL), media(self.d1 / REL))

    def test_reports_give_the_phone_path_and_hash(self):
        self._copy_without_index(keep_logs=True)
        facts = reconcile.log_facts(self.d2 / REL)
        self.assertEqual(len(facts), 4)
        self.assertTrue(all(f[0].phone_path.startswith("DCIM/Camera/") for f in facts.values()))
        status, paths, results, _v = self.backup([self.d2])
        self.assertEqual(results, [])
        txt = next(p for p in paths if str(p).endswith(".txt")).read_text(encoding="utf-8")
        self.assertIn("4 photos/videos recognised in the backup folder", txt)
        self.assertIn("4 by the phone path in the backup's reports", txt)

    def test_same_name_and_size_but_other_content_is_copied(self):
        self._copy_without_index(keep_logs=False)
        f = next((self.d2 / REL).rglob("IMG_0.jpg"))
        data = bytearray(f.read_bytes())
        data[-1] ^= 0xFF                                    # same size, different content
        f.write_bytes(bytes(data))
        status, _p, results, _v = self.backup([self.d2], hashes=True)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual([r.sf.name for r in results], ["IMG_0.jpg"])
        self.assertTrue(any(p.name == "IMG_0_1.jpg" for p in (self.d2 / REL).rglob("*.jpg")))
        self.assertEqual(f.read_bytes(), bytes(data))       # the old file stays

    def test_known_folder_is_not_scanned(self):
        self.backup([self.d1])
        set_dir = self.d1 / REL
        from phonebackup.index import BackupIndex
        idx = BackupIndex(set_dir)
        try:
            self.assertEqual(reconcile.unknown_files(set_dir, idx), {})
        finally:
            idx.close()


class SecondDrive(Base):
    def test_new_drive_gets_new_files_in_parallel_and_the_rest_drive_to_drive(self):
        self.backup([self.d1])
        self.photo("IMG_9.jpg", "2025:04:01 10:00:00")
        src = self.source()
        read = []
        orig = src.open_stream
        src.open_stream = lambda sf: (read.append(sf.rel), (yield from orig(sf)))[1]
        status, _p, results, verdict = self.backup([self.d1, self.d2], source=src)
        self.assertEqual(status, "COMPLETED", verdict)
        self.assertEqual(read, ["DCIM/Camera/IMG_9.jpg"])           # only the new one from the phone
        self.assertEqual(set(results[0].per_dest), {"Destination 1", "Destination 2"})
        self.assertEqual(media(self.d2 / REL), media(self.d1 / REL))
        self.assertEqual(len(media(self.d2 / REL)), 5)
        self.assertEqual({r[0] for r in rows(self.d2 / REL)}, {r[0] for r in rows(self.d1 / REL)})
        self.assertTrue(str(verdict).startswith("EVERYTHING"), verdict)

    def test_both_drives_complete_each_other(self):
        self.backup([self.d1])
        shutil.rmtree(self.phone)
        self.photo("IMG_7.jpg", "2025:05:01 10:00:00")
        self.backup([self.d2])                              # other photos only on drive 2
        status, _p, results, _v = self.backup([self.d1, self.d2])
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(results, [])
        self.assertEqual(media(self.d1 / REL), media(self.d2 / REL))
        self.assertEqual(len(media(self.d1 / REL)), 5)

    def test_damaged_file_on_the_source_drive_is_not_copied(self):
        self.backup([self.d1])
        f = next((self.d1 / REL).rglob("IMG_1.jpg"))
        data = bytearray(f.read_bytes())
        data[-1] ^= 0xFF
        f.write_bytes(bytes(data))
        status, paths, _r, verdict = self.backup([self.d1, self.d2])
        self.assertTrue(str(verdict).startswith("ATTENTION"), verdict)
        self.assertFalse(any(p.name == "IMG_1.jpg" for p in (self.d2 / REL).rglob("*")))
        txt = next(p for p in paths if str(p).endswith(".txt")).read_text(encoding="utf-8")
        self.assertIn("damaged", txt)


class UpdateFromOtherDrive(Base):
    """"Update from the other drive" in Manage backups – without the phone (user 2026-11-22)."""

    def test_second_drive_is_brought_up_to_date_and_compared(self):
        from phonebackup import completeness
        self.backup([self.d1])
        cfg = {"fsync": False}
        comp = completeness.compare_drives(cfg, "k", str(REL), [str(self.d1), str(self.d2)])
        self.assertEqual((comp[str(self.d1)]["missing"], comp[str(self.d2)]["missing"]), (0, 4))
        status, filled, problems = reconcile.update_drives([self.d1, self.d2], str(REL), cfg, targets=[self.d2])
        self.assertEqual((status, problems), ("COMPLETED", []))
        self.assertEqual(sum(r.copied for r in filled[str(self.d2)]), 4)
        self.assertEqual(media(self.d2 / REL), media(self.d1 / REL))
        self.assertTrue(any(p.name.startswith("Drive update") for p in (self.d2 / REL / "Logs").iterdir()))
        comp = completeness.compare_drives(cfg, "k", str(REL), [str(self.d1), str(self.d2)])
        self.assertEqual(comp[str(self.d2)]["missing"], 0)
        status, filled, _p = reconcile.update_drives([self.d1, self.d2], str(REL), cfg)
        self.assertEqual((status, filled), ("COMPLETED", {}))          # nothing left to copy

    def test_old_index_entries_do_not_count_as_missing(self):
        """Real case 2026-11-22: the up-to-date drive's list still had an old entry (same place,
        other content, backed up again later) and an entry of a file that is gone – the empty
        drive showed more missing files than the other drive has."""
        from phonebackup import completeness
        self.backup([self.d1])
        set1 = self.d1 / REL
        db = sqlite3.connect(set1 / ".phonebackup" / "index.sqlite")
        rel, = db.execute("SELECT rel_path FROM files ORDER BY rowid LIMIT 1").fetchone()
        db.execute("INSERT INTO files (source_path, size, mtime, sha256, rel_path, category) "
                   "VALUES ('import:old', 1, 0, ?, ?, 'photo')", ("0" * 64, rel))      # older content
        db.execute("UPDATE files SET rowid = -1 WHERE sha256 = ?", ("0" * 64,))
        db.execute("INSERT INTO files (source_path, size, mtime, sha256, rel_path, category) "
                   "VALUES ('import:gone', 1, 0, ?, '2020/20.01/gone.jpg', 'photo')", ("1" * 64,))
        db.commit()
        db.close()
        on_disk = len(media(set1))
        comp = completeness.compare_drives({}, "k", str(REL), [str(self.d1), str(self.d2)])
        self.assertEqual(comp[str(self.d1)]["files"], on_disk)
        self.assertEqual(comp[str(self.d2)]["missing"], on_disk)

    def test_needs_two_drives(self):
        self.backup([self.d1])
        status, _f, problems = reconcile.update_drives([self.d1, self.tmp / "gone"], str(REL), {"fsync": False})
        self.assertEqual(status, "COMPLETED WITH ERRORS")
        self.assertTrue(problems)


class DiscoverDrive(Base):
    def test_found_backup_gets_the_drive_not_the_owner_folder(self):
        """A backup found on a drive was listed with "<drive>/Sam" as its drive (screenshot 2026-11-22)."""
        from phonebackup import lastbackup
        self.backup([self.d1])
        cfg = {"destinations": [str(self.d1)]}
        lastbackup.discover(cfg)
        self.assertEqual([e["destinations"] for e in cfg["phones"].values()], [[str(self.d1)]])


class ChooseFolder(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbchoose_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_set(self, path):
        (path / ".phonebackup").mkdir(parents=True)
        (path / ".phonebackup" / "index.sqlite").write_bytes(b"")
        (path / "2025" / "25.03").mkdir(parents=True)
        (path / "2025" / "25.03" / "IMG_1.jpg").write_bytes(b"x")
        return path

    def test_drive_folder_owner_folder_and_backup_folder(self):
        s = self.make_set(self.tmp / "MMMB_Vol.1" / REL)
        for chosen in (self.tmp / "MMMB_Vol.1", self.tmp / "MMMB_Vol.1" / "Sam", s):
            c = findbackup.resolve(chosen, "Pixel 10 Pro", "Sam")
            self.assertEqual((c.action, c.base), (findbackup.USE, str(self.tmp / "MMMB_Vol.1")), chosen)

    def test_renamed_backup_folder_is_moved_into_place(self):
        old = self.tmp / "drive" / "My Pixel copy"
        old.mkdir(parents=True)
        (old / "2025").mkdir()
        (old / "2025" / "a.jpg").write_bytes(b"x")          # no index: year folders are enough
        c = findbackup.resolve(old, "Pixel 10 Pro", "Sam")
        self.assertEqual(c.action, findbackup.MOVE)
        findbackup.apply(c)
        self.assertTrue((self.tmp / "drive" / REL / "2025" / "a.jpg").is_file())
        self.assertFalse(old.exists())

    def test_empty_folder_means_new_backup_and_lists_others(self):
        self.make_set(self.tmp / "d" / "Karen" / "Galaxy A55")
        c = findbackup.resolve(self.tmp / "d", "Pixel 10 Pro", "Sam")
        self.assertEqual(c.action, findbackup.NEW)
        self.assertEqual(c.set_dir, str(self.tmp / "d" / REL))
        self.assertEqual(c.others, [str(self.tmp / "d" / "Karen" / "Galaxy A55")])

    def test_replace_missing_folder_on_the_same_drive(self):
        root = str(self.tmp / "veracrypt2")
        os.makedirs(os.path.join(root, "new"))
        old = os.path.join(root, "MSMB_Vol.01")                # renamed, does not exist any more
        other = str(self.tmp / "otherdrive" / "x")
        got = findbackup.replace_missing([old, other], os.path.join(root, "new"), [root, str(self.tmp / "otherdrive")])
        self.assertEqual(got, [other, os.path.join(root, "new")])


if __name__ == "__main__":
    unittest.main()


class ListAndCompare(Base):
    """Choose only the program's folder, pick the backup, compare it with the other drive
    (user request 2026-11-22)."""

    def test_backups_in_a_program_folder_are_listed(self):
        self.backup([self.d1])
        infos = findbackup.sets_in(self.d1)
        self.assertEqual([i.name for i in infos], ["Sam / Pixel 10 Pro"])
        self.assertEqual(infos[0].files, 4)
        self.assertTrue(infos[0].size > 0 and infos[0].last)
        self.assertEqual(len(findbackup.sets_in(self.d1 / REL)), 1)     # the backup folder itself
        self.assertEqual(findbackup.sets_in(self.phone), [])

    def test_same_backup_up_to_date(self):
        self.backup([self.d1, self.d2])
        c = findbackup.compare(self.d2 / REL, [self.d1 / REL])
        self.assertEqual((c.kind, c.shared, c.only_here, c.only_there), (findbackup.SAME, 4, 0, 0))

    def test_same_backup_with_files_missing(self):
        self.backup([self.d1, self.d2])
        self.photo("IMG_9.jpg", "2025:04:01 10:00:00")
        self.backup([self.d1])
        c = findbackup.compare(self.d2 / REL, [self.d1 / REL])
        self.assertEqual((c.kind, c.shared, c.only_there), (findbackup.BEHIND, 4, 1))

    def test_other_backup_is_different(self):
        self.backup([self.d1])
        shutil.rmtree(self.phone)
        for n in range(5):
            self.photo(f"PXL_{n}.jpg", f"2024:01:0{n + 1} 10:00:00", extra=b"other phone")
        self.backup([self.d2])
        c = findbackup.compare(self.d2 / REL, [self.d1 / REL])
        self.assertEqual((c.kind, c.shared), (findbackup.DIFFERENT, 0))

    def test_other_serial_number_is_different(self):
        from phonebackup import phoneid
        self.backup([self.d1, self.d2])
        phoneid.save(self.d1 / REL, phoneid.Record("Pixel 10 Pro", ["AAA111"], []))
        phoneid.save(self.d2 / REL, phoneid.Record("Pixel 10 Pro", ["BBB222"], []))
        c = findbackup.compare(self.d2 / REL, [self.d1 / REL])
        self.assertTrue(c.kind == findbackup.DIFFERENT and c.other_phone)

    def test_nothing_to_compare(self):
        self.backup([self.d1])
        self.assertEqual(findbackup.compare(self.d1 / REL, [self.d1 / REL, self.d2 / REL]).kind,
                         findbackup.ALONE)


class CompleteFromEachOther(Base):
    """"Prepare folders" (UI test 2026-11-23): files in a drive's list but deleted from the drive are
    copied back; a duplicate on one drive is not spread to the other."""

    def test_missing_listed_files_copied_back_without_duplicates(self):
        self.backup([self.d1, self.d2])
        set1, set2 = self.d1 / REL, self.d2 / REL
        media = sorted(p for p in set2.rglob("*.jpg"))
        gone = [p.relative_to(set2) for p in media[:2]]
        for p in media[:2]:
            p.unlink()                                        # still in hdd2's list
        orig = set1 / gone[0]
        shutil.copy(orig, orig.with_name(orig.stem + "_copy.jpg"))   # duplicate on hdd1
        status, by_drive, problems = reconcile.update_drives([self.d1, self.d2], REL, CFG,
                                                              targets=[self.d2])
        self.assertEqual(status, "COMPLETED", problems)
        for g in gone:
            self.assertTrue((set2 / g).is_file(), g)
        self.assertEqual(list(set2.rglob("*_copy.jpg")), [])
