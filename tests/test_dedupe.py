"""Duplicate check and clean-up into a review folder (user request 2026-11-22). Everything in
temporary folders – never on real backups."""

import os
import shutil
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import completeness, dedupe  # noqa: E402
from tests.test_reconcile import REL, Base, rows  # noqa: E402


def rels(set_dir):
    return sorted(r[1] for r in rows(set_dir))


class Dedupe(Base):
    def nested(self):
        """The error in the app: a new folder structure built INSIDE the old backup folder."""
        self.backup([self.d1])
        outer = self.d1 / REL
        self.backup([outer])                       # → <outer>/Sam/Pixel 10 Pro/2025/…
        return outer, outer / REL

    def test_backup_built_inside_the_old_one_is_cleaned_up(self):
        outer, inner = self.nested()
        before = completeness.present_hashes(outer)
        res = dedupe.scan(self.d1)
        self.assertEqual(len(res.groups), 4)
        for g in res.groups:                         # the outer (real) backup is kept
            self.assertEqual(g.entries[g.keep].set_dir, str(outer))
        mv = dedupe.move(res)
        self.assertEqual((mv.moved, mv.skipped), (4, []))
        review = Path(mv.review_dir)
        self.assertEqual(review.parent, self.d1)    # outside every backup folder
        self.assertTrue(dedupe.is_review_dir(review))
        self.assertEqual(completeness.present_hashes(outer), before)   # nothing lost in the backup
        self.assertEqual(rels(inner), [])            # the inner list no longer names moved files
        moved = [p for p in review.rglob("*.jpg")]
        self.assertEqual(len(moved), 4)
        self.assertTrue(any(p.suffix == ".csv" for p in review.iterdir()))
        self.assertEqual(dedupe.scan(self.d1).groups, [])   # the review folder is not checked again

    def test_put_back_undoes_everything(self):
        outer, inner = self.nested()
        before_inner = rels(inner)
        files_before = sorted(str(p) for p in self.d1.rglob("*.jpg"))
        mv = dedupe.move(dedupe.scan(self.d1))
        pb = dedupe.put_back(mv.review_dir)
        self.assertEqual((pb.restored, pb.skipped), (4, []))
        self.assertEqual(sorted(str(p) for p in self.d1.rglob("*.jpg") if "Duplicates " not in str(p)),
                         files_before)
        self.assertEqual(rels(inner), before_inner)

    def test_root_inside_a_backup_puts_the_review_folder_next_to_it(self):
        outer, _inner = self.nested()
        mv = dedupe.move(dedupe.scan(outer))
        self.assertEqual(Path(mv.review_dir).parent, outer.parent)

    def test_same_name_other_content_is_only_listed(self):
        a, b = self.tmp / "x" / "a", self.tmp / "x" / "b"
        a.mkdir(parents=True)
        b.mkdir(parents=True)
        (a / "IMG_1.jpg").write_bytes(b"one picture")
        (b / "IMG_1.jpg").write_bytes(b"another picture!")
        res = dedupe.scan(self.tmp / "x")
        self.assertEqual(res.groups, [])
        self.assertEqual([n for n, _l in res.same_name], ["IMG_1.jpg"])

    def test_file_changed_after_the_check_is_not_moved(self):
        x = self.tmp / "x"
        (x / "a").mkdir(parents=True)
        (x / "b").mkdir(parents=True)
        (x / "a" / "p.jpg").write_bytes(b"same content")
        (x / "b" / "p.jpg").write_bytes(b"same content")
        res = dedupe.scan(x)
        dup = res.groups[0].extra[0].path
        Path(dup).write_bytes(b"SAME CONTENT")       # same size, other content
        mv = dedupe.move(res)
        self.assertEqual(mv.moved, 0)
        self.assertTrue(os.path.isfile(dup))

    def test_chosen_kept_copy_in_the_same_backup_updates_its_list(self):
        self.backup([self.d1])
        s = self.d1 / REL
        first = sorted(rels(s))[0]
        copy = s / "copy" / Path(first).name
        copy.parent.mkdir()
        shutil.copy2(s / first, copy)
        res = dedupe.scan(s)
        g = res.groups[0]
        self.assertEqual(g.entries[g.keep].path, str(s / first))    # the listed copy is kept
        g.keep = next(i for i, e in enumerate(g.entries) if e.path == str(copy))   # user changes it
        mv = dedupe.move(res)
        self.assertEqual(mv.moved, 1)
        self.assertIn("copy/" + Path(first).name, rels(s))
        self.assertNotIn(first, rels(s))
        dedupe.put_back(mv.review_dir)
        self.assertIn(first, rels(s))
        self.assertTrue((s / first).is_file())


if __name__ == "__main__":
    unittest.main()


class Fingerprint(unittest.TestCase):
    """User 2026-11-23: the scan reads only the first and last 64 KB – move() must still never
    move a file that is not completely identical."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="pbfp_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_same_ends_other_middle_is_never_moved(self):
        n = 3 * dedupe.CHUNK
        a = b"A" * dedupe.CHUNK + b"x" * dedupe.CHUNK + b"Z" * dedupe.CHUNK
        b = b"A" * dedupe.CHUNK + b"y" * dedupe.CHUNK + b"Z" * dedupe.CHUNK
        (self.tmp / "one.jpg").write_bytes(a)
        (self.tmp / "two.jpg").write_bytes(b)
        (self.tmp / "three.jpg").write_bytes(a)
        res = dedupe.scan(self.tmp)
        self.assertEqual(len(res.groups), 1)                 # the fingerprint cannot tell them apart
        self.assertEqual(len(res.groups[0].entries), 3)
        self.assertEqual(res.groups[0].size, n)
        mv = dedupe.move(res)
        self.assertEqual(mv.moved, 1)                        # only the real copy of the kept file
        self.assertEqual(len(mv.skipped), 1)
        left = sorted(p.name for p in self.tmp.glob("*.jpg"))
        moved_away = sorted(p.read_bytes() == a for p in Path(mv.review_dir).rglob("*.jpg"))
        self.assertEqual(moved_away, [True])
        self.assertEqual(len(left), 2)
        self.assertIn(b, [(self.tmp / x).read_bytes() for x in left])   # the different file stays


class CancelAtOnce(unittest.TestCase):
    """User 2026-11-23: after Cancel the drives kept working – reading a file must stop at once."""

    def test_reading_stops_when_cancel_is_set(self):
        import tempfile
        import threading
        from phonebackup.copier import Cancelled, HashCancelled, sha256_file
        tmp = Path(tempfile.mkdtemp(prefix="pbcancel_"))
        try:
            f = tmp / "big.mp4"
            f.write_bytes(b"x" * (5 * 1024 * 1024))
            stop = threading.Event()
            stop.set()
            with self.assertRaises(HashCancelled):
                sha256_file(f, stop)
            self.assertTrue(issubclass(HashCancelled, Cancelled))     # every Cancel handler catches it
            shutil.copy(f, tmp / "big_1.mp4")
            res = dedupe.scan(tmp)
            self.assertEqual(res.duplicates, 1)
            mv = dedupe.move(res, cancel=stop)
            self.assertTrue(mv.cancelled)
            self.assertEqual(mv.moved, 0)
            self.assertEqual(sorted(p.name for p in tmp.glob("*.mp4")), ["big.mp4", "big_1.mp4"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class KnownHashes(unittest.TestCase):
    """User 2026-11-23: the backup lists and the reports in Logs already hold the SHA-256 – the
    duplicate search must use them instead of reading the files."""

    def setUp(self):
        from tests.test_reconcile import Base
        self.base = Base("setUp")
        self.base.setUp()

    def tearDown(self):
        self.base.tearDown()

    def test_backup_inside_backup_is_found_without_reading(self):
        b = self.base
        b.backup([b.d1])
        outer = b.d1 / REL
        b.backup([outer])                            # the error in the app: a backup inside it
        res = dedupe.scan(b.d1)
        self.assertEqual(res.hashed, 0)              # nothing read
        self.assertEqual(res.known, 8)
        self.assertEqual(res.duplicates, 4)
        self.assertTrue(all(g.sha for g in res.groups))
        read = []
        real = dedupe.sha256_file
        dedupe.sha256_file = lambda path, cancel=None: read.append(path) or real(path, cancel)
        try:
            mv = dedupe.move(res)
        finally:
            dedupe.sha256_file = real
        self.assertEqual((mv.moved, mv.skipped, read), (4, [], []))   # both sides from the lists

    def test_changed_file_is_not_trusted(self):
        b = self.base
        b.backup([b.d1])
        s = b.d1 / REL
        f = next(s.rglob("IMG_0.jpg"))
        data = f.read_bytes()
        shutil.copy(f, f.with_name("IMG_0_1.jpg"))   # unknown copy (not in the list)
        f.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))   # changed after the backup, same size
        res = dedupe.scan(b.d1)
        self.assertGreater(res.hashed, 0)            # the group had to be read
        self.assertEqual(res.duplicates, 0)          # and they are not the same any more

    def test_report_hash_alone_never_moves(self):
        b = self.base
        b.backup([b.d1])
        s = b.d1 / REL
        f = next(s.rglob("IMG_1.jpg"))
        twin = f.with_name("IMG_1_1.jpg")
        shutil.copy(f, twin)
        res = dedupe.scan(b.d1)
        self.assertEqual(res.duplicates, 1)
        g = res.groups[0]
        twin_e = next(e for e in g.entries if e.path == str(twin))
        self.assertEqual(twin_e.sha_from, "")        # not in any list or report: read
        mv = dedupe.move(res)
        self.assertEqual(mv.moved, 1)


class FromReports(KnownHashes):
    def test_report_names_the_hash_but_moving_reads_it(self):
        b = self.base
        b.backup([b.d1])
        s = b.d1 / REL
        f = next(s.rglob("IMG_2.jpg"))
        rel = f.relative_to(s).as_posix()
        db = sqlite3.connect(str(s / ".phonebackup" / "index.sqlite"))
        with db:
            db.execute("DELETE FROM files WHERE rel_path = ?", (rel,))   # list lost, report kept
        db.close()
        shutil.copy(f, f.with_name("IMG_2_1.jpg"))
        res = dedupe.scan(b.d1)
        e = next(e for g in res.groups for e in g.entries if e.path == str(f))
        self.assertEqual(e.sha_from, "report")
        read = []
        real = dedupe.sha256_file
        dedupe.sha256_file = lambda path, cancel=None: read.append(Path(path).name) or real(path, cancel)
        try:
            mv = dedupe.move(res)
        finally:
            dedupe.sha256_file = real
        self.assertEqual(mv.moved, 1)
        self.assertTrue(read)                          # report-only files are read before moving


class QuickCheck(KnownHashes):
    """User 2026-11-23: after Prepare a blind duplicate question popped up – now a quick check
    without reading comes first."""

    def test_quick_check_reads_nothing(self):
        b = self.base
        b.backup([b.d1])
        outer = b.d1 / REL
        b.backup([outer])                                   # copies with a list: on record
        stranger = next(outer.rglob("IMG_0.jpg"))
        shutil.copy(stranger, stranger.with_name("IMG_0_1.jpg"))   # a copy nobody logged
        real = dedupe.fingerprint
        dedupe.fingerprint = lambda *a: (_ for _ in ()).throw(AssertionError("read"))
        try:
            res = dedupe.scan(b.d1, read=False)
        finally:
            dedupe.fingerprint = real
        self.assertEqual(res.hashed, 0)
        self.assertGreaterEqual(res.duplicates, 3)          # the logged copies are found
        self.assertGreater(res.unchecked, 0)                # the unlogged one is reported, not read
