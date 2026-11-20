"""The Windows version has the same functions as the Linux one (user request 2026-11-20): Direct
Wi-Fi (Windows' Mobile hotspot), Bluetooth "nearby", and the freeze protection for the phone's file
transfer. Windows itself is not needed: Explorer (COM) and PowerShell are replaced by stand-ins."""
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from phonebackup import presence, sources, wireless


# ---------------------------------------------------------------- stand-ins for Explorer (COM)
class Item:
    def __init__(self, name, folder=None, data=b"", hang=None):
        self.Name = name
        self.IsFolder = folder is not None
        self.GetFolder = folder
        self.data = data
        self.Size = len(data)
        self.hang = hang
        import datetime
        self.ModifyDate = datetime.datetime(2026, 11, 20, 12, 0)

    def ExtendedProperty(self, _name):
        return self.Name


class Folder:
    def __init__(self, items, hang=None):
        self.items = items
        self.hang = hang

    def Items(self):
        if self.hang is not None:
            self.hang.wait(10)
        return list(self.items)


class Shell:
    """NameSpace(dir).CopyHere(item) writes the item's bytes into dir – or nothing (hanging phone)."""

    def __init__(self, copy=True):
        self.copy = copy
        self.threads = set()

    def NameSpace(self, path):
        shell = self
        shell.threads.add(threading.get_ident())

        class NS:
            def CopyHere(self, item, flags):
                if shell.copy:
                    (Path(path) / item.Name).write_bytes(item.data)
        return NS()


def phone(hang_dcim=None):
    camera = Folder([Item("PXL_1.jpg", data=b"x" * 1000), Item(".hidden.jpg", data=b"y")])
    dcim = Folder([Item("Camera", folder=camera)], hang=hang_dcim)
    return Folder([Item("DCIM", folder=dcim)])


class WindowsMtpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _src(self, storage, shell=None):
        src = sources.WindowsMtpSource(shell or Shell(), storage, "Pixel 10 Pro")
        src.STALL_S = 0.5
        src.CHECK_S = 0.3
        src.staging = self.tmp.name
        return src

    def test_backup_reads_through_its_own_thread(self):
        shell = Shell()
        src = self._src(phone(), shell)
        files, missing = src.list_files(["DCIM/Camera", "Pictures"])
        self.assertEqual([f.rel for f in files], ["DCIM/Camera/PXL_1.jpg"])
        self.assertEqual(missing, ["Pictures"])
        data = b"".join(src.open_stream(files[0]))
        self.assertEqual(data, b"x" * 1000)
        self.assertNotIn(threading.get_ident(), shell.threads)     # Explorer only in the worker
        self.assertTrue(src.is_connected())
        self.assertEqual(src.list_subfolders("DCIM"), ["DCIM/Camera"])

    def test_listing_that_hangs_stops(self):
        hang = threading.Event()
        src = self._src(phone(hang_dcim=hang))
        t = time.monotonic()
        with self.assertRaises(sources.MtpStalled) as cm:
            src.list_files(["DCIM"])
        self.assertLess(time.monotonic() - t, 3)
        self.assertTrue(cm.exception.abort_backup)
        self.assertFalse(src.is_connected())               # given up: no further waiting
        hang.set()

    def test_copy_that_does_not_come_stops(self):
        src = self._src(phone(), Shell(copy=False))
        files, _ = src.list_files(["DCIM/Camera"])
        t = time.monotonic()
        with self.assertRaises(sources.MtpStalled):
            b"".join(src.open_stream(files[0]))
        self.assertLess(time.monotonic() - t, 3)

    def test_finding_the_phone_that_hangs(self):
        hang = threading.Event()
        fake = types.ModuleType("win32com.client")

        class HangingShell:
            def NameSpace(self, n):
                hang.wait(10)
        fake.Dispatch = lambda name: HangingShell()
        pkg = types.ModuleType("win32com")
        pkg.client = fake
        with mock.patch.dict(sys.modules, {"win32com": pkg, "win32com.client": fake}):
            t = time.monotonic()
            src, why = sources.find_windows_mtp(timeout=0.5)
        self.assertIsNone(src)
        self.assertIn("does not answer", why)
        self.assertLess(time.monotonic() - t, 3)
        hang.set()


# ---------------------------------------------------------------- Direct Wi-Fi (Mobile hotspot)
class WindowsHotspotTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(wireless.sys, "platform", "win32")
        p.start()
        self.addCleanup(p.stop)
        wireless._win_state.update(on=False, t=-1e9)

    def test_start_stop_and_state(self):
        calls = []

        def run(script, env=None, timeout=90):
            calls.append(dict(env or {}))
            return 0, {"start": "RESULT Success ", "stop": "RESULT Success", "state": "STATE On"}[env["PB_ACTION"]]
        with mock.patch("phonebackup.winps.run", run):
            ok, msg = wireless.start_hotspot("PhoneBackup-AB12", "abcdefghjkmn")
            self.assertTrue(ok)
            self.assertEqual((calls[0]["PB_SSID"], calls[0]["PB_PASS"]), ("PhoneBackup-AB12", "abcdefghjkmn"))
            self.assertTrue(wireless.hotspot_active())
            self.assertEqual([str(n) for n in wireless.hotspot_networks()], ["192.168.137.0/24"])
            self.assertTrue(wireless.stop_hotspot()[0])

    def test_no_network_connection_says_what_to_do(self):
        with mock.patch("phonebackup.winps.run", lambda *a, **k: (0, "NOPROFILE")):
            ok, msg = wireless.start_hotspot("PhoneBackup-AB12", "abcdefghjkmn")
        self.assertFalse(ok)
        self.assertIn("settings", msg)

    def test_phone_that_joined(self):
        import ipaddress
        nets = [ipaddress.ip_network("192.168.137.0/24")]
        with mock.patch.object(wireless, "_win_neighbours",
                               lambda: [("192.168.137.1", "aa:aa:aa:aa:aa:aa"), ("192.168.137.23", "a2:b3:c4:d5:e6:f7"),
                                        ("192.0.2.9", "a2:b3:c4:d5:e6:f8")]):
            self.assertEqual(wireless.hotspot_clients(nets), ["192.168.137.23"])


# ---------------------------------------------------------------- Bluetooth "nearby"
class WindowsBluetoothTest(unittest.TestCase):
    def test_paired_phones_from_the_device_list(self):
        text = ("BTHENUM\\{0000110E-0000-1000-8000-00805F9B34FB}_LOCALMFG&0002\\7&1&0&A0B1C2D3E4F5_C00000000\tPixel 10 Pro\n"
                "BTHENUM\\DEV_A0B1C2D3E4F5\\7&2D&0&BLUETOOTHDEVICE_A0B1C2D3E4F5\tPixel 10 Pro\n"
                "USB\\VID_8087&PID_0033\\5&1\tIntel(R) Wireless Bluetooth(R)\n")
        self.assertEqual(presence._win_paired_bluetooth(text), [("A0:B1:C2:D3:E4:F5", "Pixel 10 Pro")])

    def test_in_range_only_when_the_phone_answers(self):
        with mock.patch.object(presence.sys, "platform", "win32"):
            with mock.patch("phonebackup.winps.run", lambda s, env=None, timeout=30: (0, "ERROR Success 7")) as _:
                self.assertTrue(presence.bluetooth_near("A0:B1:C2:D3:E4:F5"))
            with mock.patch("phonebackup.winps.run", lambda s, env=None, timeout=30: (0, "ERROR DeviceNotFound 0")):
                self.assertFalse(presence.bluetooth_near("A0:B1:C2:D3:E4:F5"))
            self.assertTrue(presence.bluetooth_possible())



@unittest.skipUnless(sys.platform.startswith("win"), "runs on a real Windows (GitHub's Windows test machine)")
class RealWindowsTest(unittest.TestCase):
    """The real PowerShell scripts and Explorer on Windows – no phone or Wi-Fi there, but every
    script must run without an error and give one of its known answers."""

    def test_hotspot_script_answers(self):
        ok, out = wireless._win_tether("state")
        self.assertTrue(out == "NOPROFILE" or out.startswith("STATE "), out)

    def test_bluetooth_scripts_answer(self):
        from phonebackup import winps
        code, out = winps.run(presence._WIN_PAIRED, timeout=60)
        self.assertEqual(code, 0, out)
        presence._win_paired_bluetooth(out)                  # parses whatever is there
        code, out = winps.run(presence._WIN_NEAR, {"PB_ADDR": 0xA0B1C2D3E4F5}, timeout=60)
        last = out.splitlines()[-1] if out else ""
        self.assertTrue(last == "NONE" or last.startswith("ERROR "), out)

    def test_explorer_search_runs_in_its_worker(self):
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            self.skipTest("pywin32 not installed")
        src, why = sources.find_windows_mtp(timeout=60)
        self.assertIsNone(src)                               # no phone on the test machine
        self.assertIn("no phone found", why)


if __name__ == "__main__":
    unittest.main()
