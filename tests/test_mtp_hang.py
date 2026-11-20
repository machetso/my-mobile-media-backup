"""A hanging phone file transfer (gvfs MTP) must never block the program (bug 2026-11-20: it stayed
at "connecting …" for good and no other connection could start). No real phone or mount is used."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from phonebackup import sources


class ProbeTest(unittest.TestCase):
    @unittest.skipIf(sys.platform.startswith("win"), "gvfs is Linux (':' is not allowed in Windows names)")
    def test_finds_the_phone_storage(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "mtp:host=Google_Pixel_10_Pro_PX10TEST000001" / "Internal shared storage" / "DCIM").mkdir(parents=True)
            (base / "mtp:host=Other" / "Card").mkdir(parents=True)
            mounts, dcims = sources._probe_gvfs(base)
        self.assertEqual(sorted(m.name for m in mounts), ["mtp:host=Google_Pixel_10_Pro_PX10TEST000001", "mtp:host=Other"])
        self.assertEqual([d.parent.name for d in dcims], ["Internal shared storage"])

    def test_hanging_mount_gives_up_in_time(self):
        class Hanging:
            def __init__(self, *a, **k):
                self.killed = False

            def poll(self):
                return None                  # never finishes

            def kill(self):
                self.killed = True

            def wait(self, *a, **k):
                raise AssertionError("must never wait for a hanging process")
        started = []
        with mock.patch.object(sources.subprocess, "Popen", lambda *a, **k: started.append(a[0]) or Hanging()), \
                mock.patch.object(sources.shutil, "which", lambda name: "/usr/bin/" + name), \
                mock.patch.object(sources, "_probe_gvfs", lambda base, timeout=8: None), \
                mock.patch.object(sources.os, "getuid", lambda: 4242, create=True):
            t = time.monotonic()
            src, why = sources.find_gvfs_mtp()
        self.assertIsNone(src)
        self.assertIn("does not answer", why)
        self.assertLess(time.monotonic() - t, 2)
        self.assertIn(["gio", "mount", "-s", "mtp"], started)          # the hanging mount is reset

    def test_probe_kills_and_returns_none(self):
        class Hanging:
            killed = False

            def poll(self):
                return None

            def kill(self):
                Hanging.killed = True
        with mock.patch.object(sources.subprocess, "Popen", lambda *a, **k: Hanging()), \
                mock.patch.object(sources.shutil, "which", lambda name: "/usr/bin/find"):
            t = time.monotonic()
            self.assertIsNone(sources._probe_gvfs(Path("/nowhere"), timeout=0.3))
        self.assertTrue(Hanging.killed)
        self.assertLess(time.monotonic() - t, 2)


class DuringBackupTest(unittest.TestCase):
    """The gap closed 2026-11-20: a hang DURING a backup stops it with a clear message."""

    def _source(self, d):
        src = sources.GvfsMtpSource(d, device_name="Pixel 10 Pro")
        src.STALL_S = 0.4
        src.CHECK_S = 0.3
        return src

    def test_reading_a_file_that_hangs_stops(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "DCIM").mkdir()
            (Path(d) / "DCIM" / "a.jpg").write_bytes(b"x" * 10)
            src = self._source(d)
            sf = sources.SourceFile("DCIM/a.jpg", 10, 0, "")
            self.assertEqual(b"".join(src.open_stream(sf)), b"x" * 10)     # normal: works

            def hang(path):
                time.sleep(5)
                yield b""
            with mock.patch.object(sources, "file_chunks", hang), \
                    mock.patch.object(sources, "_unmount_gvfs_mtp", lambda base=None: None):
                t = time.monotonic()
                with self.assertRaises(sources.MtpStalled) as cm:
                    b"".join(src.open_stream(sf))
            self.assertLess(time.monotonic() - t, 2)
            self.assertTrue(cm.exception.abort_backup)

    def test_listing_and_checks_that_hang(self):
        with tempfile.TemporaryDirectory() as d:
            src = self._source(d)
            (Path(d) / "DCIM").mkdir()
            (Path(d) / "DCIM" / "a.jpg").write_bytes(b"x")
            files, missing = src.list_files(["DCIM"])
            self.assertEqual([f.rel for f in files], ["DCIM/a.jpg"])

            def stuck_walk(*a, **k):
                time.sleep(5)
                return iter(())
            with mock.patch.object(sources.os, "walk", stuck_walk), \
                    mock.patch.object(sources, "_unmount_gvfs_mtp", lambda base=None: None):
                with self.assertRaises(sources.MtpStalled):
                    src.list_files(["DCIM"])
            with mock.patch.object(sources.Path, "is_dir", lambda self: time.sleep(5) or True), \
                    mock.patch.object(sources, "_unmount_gvfs_mtp", lambda base=None: None):
                t = time.monotonic()
                self.assertFalse(src.is_connected())
                self.assertLess(time.monotonic() - t, 2)

    def test_backup_stops_instead_of_waiting_for_every_file(self):
        from phonebackup import backup

        class Src:
            kind = "MTP (fallback)"

            def open_stream(self, sf):
                raise sources.MtpStalled("the phone's file transfer stopped answering")
                yield b""

            def is_connected(self):
                raise AssertionError("no retry after a hang")
        with self.assertRaises(sources.MtpStalled):
            backup._copy_one(Src(), sources.SourceFile("DCIM/a.jpg", 1, 0, ""), "photo", [], None, {},
                             mock.MagicMock())


if __name__ == "__main__":
    unittest.main()
