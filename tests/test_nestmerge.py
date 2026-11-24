"""A backup inside the backup is merged into it (user request 2026-11-23). Temporary folders only."""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import completeness, nestmerge  # noqa: E402
from tests.test_reconcile import REL, Base, media, rows  # noqa: E402


class Nested(Base):
    def setUp(self):
        super().setUp()
        self.backup([self.d1])                                      # the real backup: IMG_0..3
        self.outer = self.d1 / REL
        self.photo("IMG_ONLY.jpg", "2025:05:26 16:30:44")          # a photo only the inner one gets
        self.backup([self.outer])                                   # the mistake: a backup INSIDE it
        self.inner = self.outer / REL
        clash = self.inner / media(self.inner)[0]                  # same name, other content
        self.other = clash.read_bytes()[:-3] + b"xyz"
        changed = self.outer / media(self.inner)[0]
        changed.write_bytes(self.other)
        import os
        import time
        os.utime(changed, (time.time() + 100, time.time() + 100))   # changed later, like a real edit
        db = sqlite3.connect(str(self.outer / ".phonebackup" / "index.sqlite"))
        with db:                                                    # an old report entry, file gone
            db.execute("INSERT INTO files VALUES ('import:/old/Backup x.txt', 10, 0, ?, "
                       "'Pixel 10 Pro - Sam/Backup x.txt', 'other', '', '', '')", ("0" * 64,))
        db.close()

    def test_plan_and_merge_and_undo(self):
        before_outer = media(self.outer)
        p = nestmerge.plan(self.outer)
        self.assertEqual(Path(p.inner), self.inner)
        self.assertEqual(p.count(nestmerge.MOVE), 1)                # IMG_ONLY
        self.assertEqual(p.count(nestmerge.RENAME), 1)              # the clash
        self.assertEqual(p.count(nestmerge.DUPLICATE), 3)
        self.assertEqual(p.stale, ["Pixel 10 Pro - Sam/Backup x.txt"])
        m = nestmerge.merge(p)
        self.assertEqual((m.moved, m.duplicates, m.skipped), (2, 3, []))
        self.assertFalse((self.outer / "Sam").exists())             # the inner backup is gone
        names = [Path(r).name for r in media(self.outer)]
        self.assertIn("IMG_ONLY.jpg", names)
        self.assertTrue(any(n.endswith("_1.jpg") for n in names))   # the clash kept as _1
        review = Path(m.review_dir)
        self.assertEqual(review.parent, self.outer.parent)          # beside the backup, not in it
        self.assertTrue((review / "list of the inner backup" / "index.sqlite").is_file())
        self.assertEqual(len([f for f in review.rglob("*.jpg")]), 3)
        rels = {r[1] for r in rows(self.outer)}
        self.assertTrue(any(r.endswith("IMG_ONLY.jpg") for r in rels))
        self.assertNotIn("Pixel 10 Pro - Sam/Backup x.txt", rels)
        listed, present = completeness.listed_and_present(self.outer)
        self.assertEqual(listed - present, set())                  # every list entry has its file
        back, skipped = nestmerge.undo(review)                      # everything back
        self.assertEqual(skipped, [])
        self.assertEqual(media(self.outer), before_outer)
        self.assertTrue((self.inner / ".phonebackup" / "index.sqlite").is_file())
        self.assertEqual(sorted(Path(r).name for r in media(self.inner)).count("IMG_ONLY.jpg"), 1)
        self.assertIn("Pixel 10 Pro - Sam/Backup x.txt", {r[1] for r in rows(self.outer)})
        self.assertNotIn("IMG_ONLY.jpg", [Path(r).name for r in media(self.outer) if not r.startswith("Sam/")])
