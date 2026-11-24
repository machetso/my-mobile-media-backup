"""The backup's mark and the check "is this folder really this backup?" (user request 2026-11-23:
the app must not be fooled by a recreated folder structure). Everything in temporary folders."""

import shutil
import unittest
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import backupid, findbackup, phoneid, setfolders  # noqa: E402
from tests.test_reconcile import CFG, REL, Base, media  # noqa: E402

KEY = setfolders.key_of_rel(REL.as_posix())


class Marks(Base):
    def setUp(self):
        super().setUp()
        CFG.setdefault("backup_profiles", {}).setdefault(KEY, {}).pop("backup_id", None)

    def real(self, drive):
        self.backup([drive])
        return drive / REL

    def test_backup_marks_its_folders_with_one_id(self):
        s1 = self.real(self.d1)
        self.backup([self.d1, self.d2])
        bid = backupid.stored(CFG, KEY)
        self.assertTrue(bid)
        self.assertEqual(backupid.id_of(s1), bid)
        self.assertEqual(backupid.id_of(self.d2 / REL), bid)
        m = backupid.load(s1)
        self.assertEqual((m["owner"], m["phone"]), ("Sam", "Pixel 10 Pro"))

    def test_real_marked_folder_is_confirmed(self):
        s1 = self.real(self.d1)
        c = backupid.check(s1, backupid.stored(CFG, KEY))
        self.assertEqual(c.kind, backupid.CONFIRMED, c.reasons)
        self.assertEqual((c.files, c.listed), (4, 4))
        self.assertEqual(c.sampled, 4)

    def test_unmarked_real_folder_is_only_probable(self):
        s1 = self.real(self.d1)
        (s1 / ".phonebackup" / backupid.FILE).unlink()
        self.assertEqual(backupid.check(s1, backupid.stored(CFG, KEY)).kind, backupid.PROBABLE)

    def test_recreated_structure_is_rejected(self):
        """Same names, year folders, Logs – but no list of the program."""
        s1 = self.real(self.d1)
        fake = self.d2 / REL
        for f in media(s1):
            (fake / f).parent.mkdir(parents=True, exist_ok=True)
            (fake / f).write_bytes(b"not the photo")
        (fake / "Logs").mkdir()
        c = backupid.check(fake, backupid.stored(CFG, KEY))
        self.assertEqual(c.kind, backupid.REJECTED)

    def test_copied_list_and_mark_next_to_other_files_is_rejected(self):
        s1 = self.real(self.d1)
        fake = self.d2 / REL
        shutil.copytree(s1 / ".phonebackup", fake / ".phonebackup")      # list + mark copied
        for f in media(s1):
            (fake / f).parent.mkdir(parents=True, exist_ok=True)
            (fake / f).write_bytes(b"other content")
        c = backupid.check(fake, backupid.stored(CFG, KEY))
        self.assertEqual(c.kind, backupid.REJECTED)
        self.assertIn("SHA-256", c.reasons[0])

    def test_copied_list_without_the_files_is_rejected(self):
        s1 = self.real(self.d1)
        fake = self.d2 / REL
        shutil.copytree(s1 / ".phonebackup", fake / ".phonebackup")
        self.assertEqual(backupid.check(fake, backupid.stored(CFG, KEY)).kind, backupid.REJECTED)

    def test_whole_copy_is_the_same_backup(self):
        s1 = self.real(self.d1)
        shutil.copytree(s1, self.d2 / "Renamed" / "Folder")
        c = backupid.check(self.d2 / "Renamed" / "Folder", backupid.stored(CFG, KEY), others=[s1])
        self.assertEqual(c.kind, backupid.CONFIRMED, c.reasons)

    def test_other_mark_is_rejected_and_not_written_to(self):
        s1 = self.real(self.d1)
        backupid.write(s1, "f" * 32, "Sam", "Pixel 10 Pro")              # another backup's mark
        self.assertEqual(backupid.check(s1, backupid.stored(CFG, KEY)).kind, backupid.REJECTED)
        before = media(s1)
        self.photo("IMG_9.jpg", "2025:03:19 10:00:00")
        self.backup([self.d1, self.d2])                                 # d1 skipped, d2 used
        self.assertEqual(media(s1), before)
        self.assertIn("2025/25.03/IMG_9.jpg", "\n".join(media(self.d2 / REL)))
        with self.assertRaises(RuntimeError):
            self.backup([self.d1])

    def test_other_phone_serial_is_rejected(self):
        s1 = self.real(self.d1)
        phoneid.save(s1, phoneid.Record("Pixel 10 Pro", ["SERIAL-B"], []))
        c = backupid.check(s1, backupid.stored(CFG, KEY), serials=["SERIAL-A"])
        self.assertEqual(c.kind, backupid.REJECTED)

    def test_other_backup_content_is_rejected(self):
        s1 = self.real(self.d1)
        for n in range(4):                                              # another phone's photos
            self.photo(f"IMG_{n}.jpg", f"2024:01:1{n} 10:00:00", extra=b"other")
        CFG["backup_profiles"][KEY].pop("backup_id")
        self.backup([self.d2])
        CFG["backup_profiles"][KEY].pop("backup_id")
        for s in (s1, self.d2 / REL):
            (s / ".phonebackup" / backupid.FILE).unlink()
        c = backupid.check(self.d2 / REL, "", others=[s1])
        self.assertEqual(c.kind, backupid.REJECTED)

    def test_id_is_taken_over_from_the_marks(self):
        s1 = self.real(self.d1)
        bid = backupid.stored(CFG, KEY)
        CFG["backup_profiles"][KEY].pop("backup_id")                    # e.g. another computer
        self.assertEqual(backupid.resolve(CFG, KEY, [str(s1)], create=False), (bid, False))


class Search(Base):
    def test_finds_backups_whatever_they_are_called(self):
        self.backup([self.d1 / "MMMB_Vol.1"])
        shutil.copytree(self.d1 / "MMMB_Vol.1" / REL, self.d2 / "old" / "Somebody" / "Phone")
        (self.d2 / "fake" / "Sam" / "Pixel 10 Pro" / "2025").mkdir(parents=True)
        found = sorted(findbackup.search_any([self.d1, self.d2]))
        self.assertEqual(found, sorted([str(self.d1 / "MMMB_Vol.1" / REL),
                                        str(self.d2 / "old" / "Somebody" / "Phone")]))

    def test_placed(self):
        s = self.tmp / "MMMB_Vol.1" / REL
        self.assertEqual(findbackup.placed(s, "Pixel 10 Pro", "Sam"),
                         (str(self.tmp / "MMMB_Vol.1"), str(s), findbackup.USE))
        base, target, action = findbackup.placed(self.tmp / "V" / "Somebody" / "Phone", "Pixel 10 Pro", "Sam")
        self.assertEqual((base, target, action), (str(self.tmp / "V"), str(self.tmp / "V" / REL), findbackup.MOVE))


class Follow(Base):
    """Two VeraCrypt volumes opened in the other order: /media/veracrypt1 ↔ veracrypt2 (2026-11-23)."""

    def setUp(self):
        super().setUp()
        CFG.setdefault("backup_profiles", {}).setdefault(KEY, {}).pop("backup_id", None)
        self.vc1, self.vc2 = self.tmp / "veracrypt1", self.tmp / "veracrypt2"
        self.a = self.vc2 / "2nd Backup" / "MMMB_Vol.1"        # as remembered
        self.b = self.vc1 / "MMMB_Vol.2"
        self.backup([self.a, self.b])
        from phonebackup import backuplist
        backuplist.save_profile(CFG, KEY, destinations=[str(self.a), str(self.b)])
        CFG.setdefault("phones", {}).setdefault(KEY, {"phone": "Pixel 10 Pro", "owner": "Sam"})

    def swap(self):
        tmp = self.tmp / "x"
        self.vc1.rename(tmp)
        self.vc2.rename(self.vc1)
        tmp.rename(self.vc2)

    def dests(self):
        return CFG["backup_profiles"][KEY]["destinations"]

    def test_swapped_volumes_are_followed(self):
        self.swap()
        changes = backupid.follow(CFG, [str(self.vc1), str(self.vc2)])
        self.assertEqual(len(changes), 2)
        self.assertEqual(self.dests(), [str(self.vc1 / "2nd Backup" / "MMMB_Vol.1"), str(self.vc2 / "MMMB_Vol.2")])
        self.assertEqual(backupid.follow(CFG, [str(self.vc1), str(self.vc2)]), [])     # nothing left

    def test_unmarked_folder_is_not_followed(self):
        for d in (self.a, self.b):
            (d / REL / ".phonebackup" / backupid.FILE).unlink()
        self.swap()
        self.assertEqual(backupid.follow(CFG, [str(self.vc1), str(self.vc2)]), [])
        self.assertEqual(self.dests(), [str(self.a), str(self.b)])

    def test_recreated_folder_with_the_same_path_is_not_followed(self):
        shutil.rmtree(self.vc2)
        fake = self.vc1 / "2nd Backup" / "MMMB_Vol.1" / REL / ".phonebackup"
        fake.mkdir(parents=True)
        backupid.write(fake.parent, "e" * 32, "Sam", "Pixel 10 Pro")       # another backup's mark
        self.assertEqual(backupid.follow(CFG, [str(self.vc1)]), [])
        (fake / backupid.FILE).unlink()                                    # no mark at all
        self.assertEqual(backupid.follow(CFG, [str(self.vc1)]), [])


class SearchBigDrive(Base):
    """User 2026-11-23: /media/veracrypt2/MMMB_Vol.2 was not found – a big "Backups" folder on the
    same drive used up the whole search time."""

    def setUp(self):
        super().setUp()
        self.backup([self.d1 / "MMMB_Vol.2"])
        for i in range(30):
            for j in range(30):
                (self.d1 / "Backups" / f"a{i:02}" / f"b{j:02}").mkdir(parents=True)

    def test_quick_place_of_the_program(self):
        found = findbackup.search_any([self.d1], rel=REL.as_posix(), max_dirs=5)
        self.assertEqual(found, [str(self.d1 / "MMMB_Vol.2" / REL)])

    def test_level_by_level_without_names(self):
        found = findbackup.search_any([self.d1], max_dirs=40)
        self.assertEqual(found, [str(self.d1 / "MMMB_Vol.2" / REL)])

    def test_chosen_folder_is_the_backup_folder_itself(self):
        s = self.d1 / "MMMB_Vol.2" / REL
        self.assertEqual(findbackup.search_any([s], rel=REL.as_posix()), [str(s)])
        self.assertEqual(findbackup.search_any([self.d1 / "MMMB_Vol.2"], rel=REL.as_posix()), [str(s)])


class OneDrive(Base):
    def test_alone_drive_is_compared_with_its_list_and_the_other_drive(self):
        from phonebackup import completeness
        self.backup([self.d1, self.d2])
        cfg = {"drive_state": {}}
        completeness.config.save, saved = (lambda c: None), completeness.config.save
        try:
            completeness.compare_drives(cfg, KEY, REL.as_posix(), [str(self.d1), str(self.d2)])
            shutil.rmtree(self.d2)                                         # only d1 is connected
            (self.d1 / REL / media(self.d1 / REL)[0]).unlink()             # a file of its list is gone
            r = completeness.compare_drives(cfg, KEY, REL.as_posix(), [str(self.d1), str(self.d2)])
        finally:
            completeness.config.save = saved
        self.assertTrue(r[str(self.d1)]["alone"])
        self.assertEqual(r[str(self.d1)]["own_missing"], 1)
        self.assertEqual((r[str(self.d1)]["other_files"], r[str(self.d1)]["files"]), (4, 3))


HAVE_QT = importlib.util.find_spec("PySide6") is not None      # GitHub's test machines: no PySide6


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class PrepareShowsFiles(Base):
    """User 2026-11-23: "Prepare folders" must show WHAT it is doing, not only "Working …"."""

    def test_status_names_the_files(self):
        from phonebackup import completeness, dedupe, reconcile, ui
        from phonebackup.gui_backups import _progress_to_ui

        class Catch:
            def __init__(self):
                self.lines, self.said = [], []

            def log(self, level, text):
                pass

            def progress(self, d):
                self.lines.append(d["current"])

            def status(self, text):
                self.said.append(text)
        self.backup([self.d1])
        shutil.copy(next((self.d1 / REL).rglob("IMG_0.jpg")), self.d1 / REL / "IMG_0 copy.jpg")
        c = Catch()
        ui.set_handler(c)
        saved, completeness.config.save = completeness.config.save, (lambda cfg: None)
        try:
            ui.status("Listing the files on hdd1 …")
            dedupe.scan(self.d1 / REL, progress=_progress_to_ui("Looking for duplicates on hdd1"))
            (self.d2 / REL).mkdir(parents=True)
            reconcile.update_drives([str(self.d1), str(self.d2)], REL.as_posix(), {})
        finally:
            ui.set_handler(None)
            completeness.config.save = saved
        self.assertEqual(c.said, ["Listing the files on hdd1 …"])
        self.assertTrue(any(x.startswith("Looking for duplicates on hdd1: IMG_0") for x in c.lines), c.lines)
        self.assertTrue(any(x.endswith(".jpg → hdd2") for x in c.lines), c.lines)


class OldEntryOfAPlace(Base):
    """User 2026-11-23: 19 RAW files were refused as "damaged": their place had an OLD list entry
    (an import of an old drive, other content, same size) before the current one."""

    def test_copy_uses_the_newest_entry(self):
        import sqlite3
        from phonebackup import completeness, reconcile
        self.backup([self.d1])
        s1 = self.d1 / REL
        db = sqlite3.connect(str(s1 / ".phonebackup" / "index.sqlite"))
        rel, real = db.execute("SELECT rel_path, source_path FROM files ORDER BY rowid LIMIT 1").fetchone()
        row = db.execute("SELECT * FROM files WHERE rel_path=?", (rel,)).fetchone()
        with db:
            db.execute("DELETE FROM files WHERE rel_path=?", (rel,))
            old = list(row)
            old[0], old[3] = "import:/old drive/" + rel, "0" * 64          # older import, other content
            db.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?)", old)
            db.execute("INSERT INTO files VALUES (?,?,?,?,?,?,?,?,?)", row)   # the current entry, newer
        db.close()
        (self.d2 / REL).mkdir(parents=True)
        saved, completeness.config.save = completeness.config.save, (lambda c: None)
        try:
            status, by_drive, problems = reconcile.update_drives([str(self.d1), str(self.d2)], REL.as_posix(), {})
        finally:
            completeness.config.save = saved
        errors = [e for lst in by_drive.values() for r in lst for e in r.errors]
        self.assertEqual(errors, [])
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(completeness.present_hashes(self.d2 / REL), completeness.present_hashes(s1))

    def test_old_entry_does_not_count_as_already_there(self):
        from phonebackup.index import BackupIndex
        self.backup([self.d1])
        idx = BackupIndex(self.d1 / REL)
        try:
            rel, size, sha = idx.db.execute("SELECT rel_path, size, sha256 FROM files LIMIT 1").fetchone()
            idx.add("import:/old/x", size, 0, "1" * 64, rel, "photo", "", "")   # newer entry, other content
            idx.commit()
            self.assertIsNone(idx.find_by_sha(sha))          # the place now holds other content
            self.assertEqual(idx.sha_for_rel(rel, size), "1" * 64)
        finally:
            idx.close()


class WholeFolderCompared(Base):
    """User 2026-11-23: "up to date" on both drives, but different file counts – the comparison
    only knew the files of the lists."""

    def test_files_outside_the_list_are_compared_too(self):
        from phonebackup import completeness
        self.backup([self.d1, self.d2])
        extra = self.d1 / REL / "Alex" / "Pixel 10 Pro" / "2026" / "26.05" / "PXL_raw.dng"   # nested, unlisted
        extra.parent.mkdir(parents=True)
        extra.write_bytes(b"raw photo")
        saved, completeness.config.save = completeness.config.save, (lambda c: None)
        try:
            r = completeness.compare_drives({}, KEY, REL.as_posix(), [str(self.d1), str(self.d2)])
        finally:
            completeness.config.save = saved
        self.assertEqual((r[str(self.d1)]["missing"], r[str(self.d2)]["missing"]), (0, 1))
        self.assertEqual(r[str(self.d1)]["files"], r[str(self.d2)]["files"] + 1)

    def test_list_entry_without_file_is_shown_not_missing(self):
        from phonebackup import completeness
        self.backup([self.d1, self.d2])
        for d in (self.d1, self.d2):
            (d / REL / media(d / REL)[0]).unlink()
        saved, completeness.config.save = completeness.config.save, (lambda c: None)
        try:
            r = completeness.compare_drives({}, KEY, REL.as_posix(), [str(self.d1), str(self.d2)])
        finally:
            completeness.config.save = saved
        self.assertEqual(r[str(self.d1)]["missing"], 0)
        self.assertEqual(r[str(self.d1)]["own_missing"], 1)
        self.assertEqual(r[str(self.d1)]["files"], 3)
