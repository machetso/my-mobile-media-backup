"""Integrity check (user request 2026-11-23). Everything in temporary folders."""

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import integrity, knownhash  # noqa: E402
from tests.test_reconcile import REL, Base, media  # noqa: E402


class Integrity(Base):
    def setUp(self):
        super().setUp()
        self.backup([self.d1])
        self.s = self.d1 / REL

    def test_all_unchanged(self):
        r = integrity.run(self.s)
        self.assertEqual((r.ok, r.changed, r.new, r.gone, r.unreadable), (4, [], [], [], []))

    def test_damaged_file_with_same_size_and_time_is_found(self):
        f = self.s / media(self.s)[0]
        st = os.stat(f)
        data = bytearray(f.read_bytes())
        data[len(data) // 2] ^= 0xFF                       # one bit flipped in the middle
        f.write_bytes(bytes(data))
        os.utime(f, (st.st_atime, st.st_mtime))             # size and time as before
        r = integrity.run(self.s)
        self.assertEqual(r.ok, 3)
        self.assertEqual([c[0] for c in r.changed], [media(self.s)[0]])
        self.assertEqual(r.changed[0][3], "list")

    def test_new_and_gone_and_save_and_report(self):
        (self.s / media(self.s)[1]).unlink()
        extra = self.s / "old" / "IMG_9.jpg"
        extra.parent.mkdir()
        extra.write_bytes(b"photo without record")
        r = integrity.run(self.s)
        self.assertEqual(r.new, ["old/IMG_9.jpg"])
        self.assertEqual(len(r.gone), 1)
        integrity.save(r)
        self.assertEqual(knownhash.known(self.s)[1], [])     # now on record ("checked")
        txt = Path(integrity.write_report(r))
        self.assertTrue(txt.is_file() and txt.parent.name == "Logs")
        self.assertIn("IMG_9.jpg", txt.read_text(encoding="utf-8"))
        self.assertTrue(txt.with_suffix(".csv").is_file())
        r2 = integrity.run(self.s)                           # the saved checksum is used next time
        self.assertEqual((r2.new, r2.changed), ([], []))

    def test_list_is_never_changed(self):
        idx = self.s / ".phonebackup" / "index.sqlite"
        before = idx.read_bytes()
        r = integrity.run(self.s)
        integrity.save(r)
        integrity.write_report(r)
        self.assertEqual(idx.read_bytes(), before)

    def test_cancel(self):
        stop = threading.Event()
        stop.set()
        r = integrity.run(self.s, cancel=stop)
        self.assertTrue(r.cancelled)
        self.assertEqual(r.checked, 0)
