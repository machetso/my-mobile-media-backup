"""A running backup continues over a faster connection (user request 2026-11-17)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup.backup import SourceSwitch, perform_backup  # noqa: E402
from phonebackup.report import LOGS_DIR  # noqa: E402
from phonebackup.sources import FolderSource  # noqa: E402
from tests.test_all import jpeg_with_exif  # noqa: E402


class SlowSource(FolderSource):
    """Offers the faster connection while the first file is copied."""

    def __init__(self, root, switch, fast):
        super().__init__(root, device_name="Pixel 10 Pro")
        self.switch, self.fast, self.read = switch, fast, []
        self.kind = "Wi-Fi (phone app)"

    def open_stream(self, sf):
        self.read.append(sf.rel)
        self.switch.offer(self.fast, lambda old, new: self.events.append((old, new)))
        yield from super().open_stream(sf)


class CableSource(FolderSource):
    """The cable is pulled while the second file is read (user request 2026-11-23)."""

    def __init__(self, root):
        super().__init__(root, device_name="Pixel 10 Pro")
        self.kind = "USB cable (ADB)"
        self.read, self.gone = [], False

    def is_connected(self):
        return not self.gone

    def open_stream(self, sf):
        self.read.append(sf.rel)
        if len(self.read) == 2:
            self.gone = True
            yield b"\xff\xd8"
            raise OSError("device not found")
        yield from super().open_stream(sf)


class Switch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pbswitch_"))
        self.phone, self.d = self.tmp / "phone", self.tmp / "hdd"
        self.d.mkdir()
        for n in range(4):
            p = self.phone / "DCIM/Camera" / f"IMG_{n}.jpg"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(jpeg_with_exif(f"2025:03:1{n} 10:00:00"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_continues_over_new_connection(self):
        sw = SourceSwitch()
        fast = FolderSource(self.phone, device_name="Pixel 10 Pro")
        fast.kind = "USB cable (ADB)"
        fast_read = []
        orig = fast.open_stream
        fast.open_stream = lambda sf: (fast_read.append(sf.rel), (yield from orig(sf)))[1]
        slow = SlowSource(self.phone, sw, fast)
        slow.events = []
        status, paths, results, _ = perform_backup(slow, "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d],
                                                   {"fsync": False}, interactive=False, switch=sw)
        self.assertEqual(status, "COMPLETED")
        self.assertEqual(len(slow.read), 1)                  # first file over the slow connection
        self.assertEqual(len(fast_read), 3)                  # the rest over the fast one
        self.assertEqual(len(slow.events), 1)
        self.assertTrue(all(r.ok for r in results))
        report = next(p for p in paths if str(p).endswith(".txt")).read_text(encoding="utf-8")
        self.assertIn("Connection changes", report)
        self.assertIn("Wi-Fi (phone app) → USB cable (ADB) (after 1 of 4 files)", report)
        self.assertTrue((self.d / "Sam" / "Pixel 10 Pro" / LOGS_DIR).is_dir())

    def test_cable_pulled_continues_over_wifi(self):
        """Cable pulled during a file: the backup waits, continues over Wi-Fi, copies that file
        again – COMPLETED, nothing missing (user request 2026-11-23)."""
        import threading
        sw = SourceSwitch(patience=lambda: 10)
        cable = CableSource(self.phone)
        wifi = FolderSource(self.phone, device_name="Pixel 10 Pro")
        wifi.kind = "Wi-Fi (phone app)"

        def watcher():                       # the window's watcher: finds the phone over Wi-Fi
            if sw.lost.wait(10):
                sw.offer(wifi)
        threading.Thread(target=watcher, daemon=True).start()
        status, paths, results, _ = perform_backup(cable, "Pixel 10 Pro", "Sam", ["DCIM/Camera"], [self.d],
                                                   {"fsync": False}, interactive=False, switch=sw)
        self.assertEqual(status, "COMPLETED")
        self.assertTrue(all(r.ok for r in results), [r.transfer_check for r in results])
        self.assertEqual(len(list((self.d / "Sam" / "Pixel 10 Pro").rglob("IMG_*.jpg"))), 4)
        report = next(p for p in paths if str(p).endswith(".txt")).read_text(encoding="utf-8")
        self.assertIn("USB cable (ADB) → Wi-Fi (phone app) (after 1 of 4 files)", report)

    def test_no_other_way_is_incomplete(self):
        sw = SourceSwitch(patience=lambda: 1)
        status, _p, _r, _ = perform_backup(CableSource(self.phone), "Pixel 10 Pro", "Sam", ["DCIM/Camera"],
                                           [self.d], {"fsync": False}, interactive=False, switch=sw)
        self.assertEqual(status, "ABORTED (phone disconnected)")


if __name__ == "__main__":
    unittest.main()
