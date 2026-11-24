"""The backup's file list for "not backed up yet" (user request 2026-11-23). Settings in a temporary folder."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonebackup import knownlist, presence  # noqa: E402


def make_index(set_dir, rows):
    d = Path(set_dir) / ".phonebackup"
    d.mkdir(parents=True)
    db = sqlite3.connect(d / "index.sqlite")
    db.execute("CREATE TABLE files(source_path TEXT, size INTEGER, backed_up_at TEXT)")
    db.executemany("INSERT INTO files VALUES (?,?,?)", rows)
    db.commit()
    db.close()


class KnownListTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.t / "cfg"), "APPDATA": str(self.t / "cfg")})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_vectors_like_the_phone(self):          # KnownListTest.kt has the same numbers
        b = knownlist.pack([knownlist.digest("DCIM/Camera/PXL_1.jpg", 1234), knownlist.digest("DCIM/Camera/VID_2.mp4", 99)])
        self.assertEqual(b.hex(), "db15a664763a65264d184e19b0ea6d10")
        self.assertEqual(knownlist.version(b), "534edaef8823e080")
        self.assertEqual(presence.known_proof("ab" * 32, "pc1", "0123456789abcdef", 1800000000, "534edaef8823e080"),
                         "13e8803734aef850ae9a38667344c77c")

    def test_newest_connected_list_then_remembered(self):
        a, b = self.t / "A" / "set", self.t / "B" / "set"
        make_index(a, [("DCIM/Camera/1.jpg", 10, "2026-11-20 10:00:00")])
        make_index(b, [("DCIM/Camera/1.jpg", 10, "2026-11-20 10:00:00"), ("DCIM/Camera/2.jpg", 20, "2026-11-23 13:00:00")])
        self.assertEqual(knownlist.current("K"), ("", ""))          # nothing known: by date
        got = knownlist.refresh("K", [str(a), str(b)])
        self.assertEqual(got["from"], str(b))
        files = [("DCIM/Camera/1.jpg", 10), ("DCIM/Camera/2.jpg", 20), ("DCIM/Camera/3.mp4", 30), ("DCIM/x.txt", 1)]
        self.assertEqual(knownlist.count(files, got["blob"]), (0, 1, 30))
        # no drive connected: the remembered list
        self.assertEqual(knownlist.refresh("K", [str(self.t / "gone")])["k"], got["k"])
        # only the older drive connected: its list is the actual one
        self.assertEqual(knownlist.refresh("K", [str(a)])["from"], str(a))

    def test_phone_list_remembered_per_folders(self):
        knownlist.save_phone("K", [("DCIM/Camera/1.jpg", 10)], ["DCIM/Camera"])
        self.assertEqual(knownlist.load_phone("K", ["DCIM/Camera"]), [("DCIM/Camera/1.jpg", 10)])
        self.assertIsNone(knownlist.load_phone("K", ["DCIM/Camera", "Pictures"]))

    def test_list_sent_only_when_the_phone_has_another(self):
        cfg = {}
        entry = {"secret": "ab" * 32}
        answers = [{"photos": 5, "videos": 0, "k": ""}]
        with mock.patch.object(presence.companion, "pc_identity", lambda c: ("pc1", "x")), \
                mock.patch.object(presence, "send_known", return_value=(1, 0, 7)) as sk, \
                mock.patch("urllib.request.OpenerDirector.open") as op:
            op.return_value.__enter__.return_value.read.side_effect = lambda n: __import__("json").dumps(answers[0]).encode()
            self.assertEqual(presence.ask_new(cfg, entry, "a:1", 0, ["DCIM"], known=("abcd", "ZA==")), (1, 0, 7))
            self.assertEqual(sk.call_count, 1)
            answers[0] = {"photos": 5, "videos": 0, "k": "abcd"}
            self.assertEqual(presence.ask_new(cfg, entry, "a:1", 0, ["DCIM"], known=("abcd", "ZA==")), (5, 0, None))
            answers[0] = {"photos": 5, "videos": 0}                   # older phone app: no list
            self.assertEqual(presence.ask_new(cfg, entry, "a:1", 0, ["DCIM"], known=("abcd", "ZA==")), (5, 0, None))
            self.assertEqual(sk.call_count, 1)


if __name__ == "__main__":
    unittest.main()
