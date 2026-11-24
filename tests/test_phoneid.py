"""Never mix up phones: the backup folder remembers its phone (user requirement 2026-11-04)."""
import sys
import tempfile
import unittest
from pathlib import Path

from phonebackup import phoneid as P

SAMSUNG_USB = P.PhoneId("SM-G780G", "samsung", "RF8TEST0001", "", "usb-adb")
SAMSUNG_APP = P.PhoneId("SM-G780G", "samsung", "", "app-samsung", "app-wifi")
SAMSUNG_LINKED = P.PhoneId("SM-G780G", "samsung", "RF8TEST0001", "app-samsung", "usb-adb")
PIXEL_APP = P.PhoneId("Pixel 10 Pro", "Google", "", "app-pixel", "app-wifi")
PIXEL_USB = P.PhoneId("Pixel 10 Pro", "Google", "PX10TEST000001", "", "usb-adb")
OTHER_S20 = P.PhoneId("SM-G780G", "samsung", "OTHERSERIAL", "", "usb-adb")


class PhoneIdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name) / "Galaxy A55 - Kim"

    def tearDown(self):
        self.tmp.cleanup()

    def test_todays_mixup_is_refused(self):
        """Samsung backed up over the cable, then the Pixel turns up over Wi-Fi → refused."""
        P.learn(self.parent, SAMSUNG_USB, P.compare(P.load(self.parent), SAMSUNG_USB))
        self.assertEqual(P.compare(P.load(self.parent), PIXEL_APP), P.MISMATCH)
        self.assertEqual(P.compare(P.load(self.parent), PIXEL_USB), P.MISMATCH)

    def test_same_phone_other_connection(self):
        P.learn(self.parent, SAMSUNG_LINKED, P.NEW)       # cable + app verified: both ids known
        for pid in (SAMSUNG_USB, SAMSUNG_APP, SAMSUNG_LINKED):
            self.assertEqual(P.compare(P.load(self.parent), pid), P.MATCH, pid)

    def test_other_phone_same_model_is_refused(self):
        P.learn(self.parent, SAMSUNG_USB, P.NEW)
        self.assertEqual(P.compare(P.load(self.parent), OTHER_S20), P.MISMATCH)

    def test_model_only_is_probable_and_learns_nothing(self):
        P.learn(self.parent, SAMSUNG_USB, P.NEW)
        self.assertEqual(P.compare(P.load(self.parent), SAMSUNG_APP), P.PROBABLE)
        P.learn(self.parent, SAMSUNG_APP, P.PROBABLE)
        self.assertEqual(P.load(self.parent).app_ids, [])

    def test_new_folder(self):
        self.assertEqual(P.compare(P.load(self.parent), PIXEL_APP), P.NEW)
        P.learn(self.parent, PIXEL_APP, P.NEW)
        self.assertEqual(P.load(self.parent).app_ids, ["app-pixel"])

    def test_phone_app_paired_again_same_phone(self):
        """2026-11-22: the phone app was paired anew (new app id) – the backup of the SAME phone
        must not be refused. Over Wi-Fi the app gives the serial confirmed over the cable."""
        old = P.PhoneId("Pixel 10 Pro", "Google", "PX10TEST000001", "app-old", "usb-adb")
        P.learn(self.parent, old, P.NEW)
        new_app_wifi = P.PhoneId("Pixel 10 Pro", "Google", "PX10TEST000001", "app-new", "app-wifi")
        self.assertEqual(P.compare(P.load(self.parent), new_app_wifi), P.MATCH)
        P.learn(self.parent, new_app_wifi, P.MATCH)
        self.assertEqual(P.load(self.parent).app_ids, ["app-old", "app-new"])
        no_serial = P.PhoneId("Pixel 10 Pro", "Google", "", "app-other", "app-wifi")
        self.assertEqual(P.compare(P.load(self.parent), no_serial), P.PROBABLE)   # asked, not refused
        other = P.PhoneId("Pixel 10 Pro", "Google", "OTHER0000001", "app-new", "usb-adb")
        self.assertEqual(P.compare(P.load(self.parent), other), P.MISMATCH)      # other serial: refused

    def test_phone_app_gives_the_paired_serial(self):
        from phonebackup.companion import CompanionSource

        class Client:
            def request(self, method, path):
                return {"model": "Pixel 10 Pro", "manufacturer": "Google", "phone_id": "app-new"}
        src = CompanionSource.__new__(CompanionSource)
        src.client, src.device_name = Client(), "Pixel 10 Pro"
        src.entry = {"phone_id": "app-new", "serial": "PX10TEST000001"}
        pid = P.identify(src)
        self.assertEqual((pid.serial, pid.app_id, pid.connection), ("PX10TEST000001", "app-new", "app-wifi"))

    def test_files_in_common_are_evidence(self):
        """2026-11-22: no serial – the photos the phone and the backup have in common decide how
        likely it is the right backup (a sample checked with the phone's SHA-256)."""
        import shutil
        from phonebackup.backup import perform_backup
        from phonebackup.sources import FolderSource
        from tests.test_all import jpeg_with_exif
        tmp = Path(self.tmp.name)
        for n in range(5):
            p = tmp / "phone" / "DCIM/Camera" / f"IMG_{n}.jpg"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(jpeg_with_exif(f"2025:03:1{n} 10:00:00"))
        perform_backup(FolderSource(tmp / "phone", device_name="Pixel 10 Pro"), "Pixel 10 Pro", "Sam",
                       ["DCIM/Camera"], [tmp / "hdd"], {"fsync": False}, interactive=False)
        parent = tmp / "hdd" / "Sam" / "Pixel 10 Pro"
        src = FolderSource(tmp / "phone", device_name="Pixel 10 Pro", verify_source=True)
        o = P.overlap(src, src.list_files(["DCIM/Camera"])[0], parent)
        self.assertEqual((o.phone_files, o.same, o.hashed, o.hash_same, o.strong), (5, 5, 5, 5, True))
        self.assertIn("5 of the 5 photos and videos on the phone are already in this backup", P.overlap_text(o))
        shutil.rmtree(tmp / "phone")
        (tmp / "phone" / "DCIM/Camera").mkdir(parents=True)
        (tmp / "phone" / "DCIM/Camera" / "IMG_X.jpg").write_bytes(jpeg_with_exif("2025:06:01 10:00:00"))
        o = P.overlap(src, src.list_files(["DCIM/Camera"])[0], parent)
        self.assertTrue(o.none)
        self.assertFalse(o.strong)
        self.assertIn("probably a different phone", P.overlap_text(o))

    def test_double_check(self):
        self.assertTrue(P.same_phone(SAMSUNG_LINKED, SAMSUNG_USB))
        self.assertFalse(P.same_phone(SAMSUNG_USB, OTHER_S20))
        self.assertFalse(P.same_phone(SAMSUNG_APP, PIXEL_APP))

    def test_speed_advice(self):
        self.assertTrue(P.speed_advice(SAMSUNG_USB, 5000)[0])
        fast, text = P.speed_advice(SAMSUNG_USB, 480)
        self.assertFalse(fast)
        self.assertIn("USB 3", text)
        fast, text = P.speed_advice(PIXEL_APP)
        self.assertFalse(fast)
        self.assertIn("“Allow backup”", text)            # the phone app's switch (renamed 2026-11-20)


class OldReportTest(unittest.TestCase):
    def test_identity_from_old_report(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Backup Galaxy A55 Kim 2026-11-04.txt").write_text(
                "  Smartphone       : SM-G780G\n"
                "  Connection       : ADB - ADB (USB debugging), serial RF8TEST0001, Android 13\n",
                encoding="utf-8")
            (Path(d) / "Backup Galaxy A55 Kim 2026-11-05.txt").write_text(
                "  Smartphone       : SM-G780G\n"
                "  Connection       : ADB over Wi-Fi - ADB (Wi-Fi), serial 192.168.1.5:4321, Android 13\n",
                encoding="utf-8")
            rec = P.load(d)
            self.assertEqual((rec.model, rec.serials), ("SM-G780G", ["RF8TEST0001"]))
            self.assertEqual(P.compare(rec, PIXEL_APP), P.MISMATCH)
            self.assertEqual(P.compare(rec, SAMSUNG_USB), P.MATCH)
            self.assertEqual(P.compare(rec, SAMSUNG_APP), P.PROBABLE)

    def test_identity_from_report_in_logs_folder(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Logs").mkdir()
            (Path(d) / "Logs" / "Backup Galaxy A55 Kim 2026-11-11.txt").write_text(
                "  Smartphone       : SM-G780G\n"
                "  Connection       : ADB - ADB (USB debugging), serial RF8TEST0002, Android 13\n",
                encoding="utf-8")
            (Path(d) / "Backup Galaxy A55 Kim 2026-11-04.txt").write_text(      # old place
                "  Smartphone       : SM-G780G\n"
                "  Connection       : ADB - ADB (USB debugging), serial RF8TEST0001, Android 13\n",
                encoding="utf-8")
            rec = P.load(d)
            self.assertEqual((rec.model, sorted(rec.serials)), ("SM-G780G", ["RF8TEST0001", "RF8TEST0002"]))


class CableAdviceTest(unittest.TestCase):
    def test_phone_already_on_cable(self):
        fast, text = P.speed_advice(SAMSUNG_APP, 5000, "Samsung phone")
        self.assertFalse(fast)
        self.assertIn("already on the USB cable (USB 3)", text)
        self.assertNotIn("plug the phone in", text)

    def test_samsung_name_on_cable(self):
        import tempfile as tf
        from phonebackup import adbsetup
        with tf.TemporaryDirectory() as d:
            p = Path(d) / "4-1"
            p.mkdir()
            (p / "idVendor").write_text("04e8")
            (p / "manufacturer").write_text("SAMSUNG")
            (p / "product").write_text("SAMSUNG_Android")
            self.assertEqual(adbsetup._linux_usb_phones(d), ["Samsung phone"])

    @unittest.skipIf(sys.platform.startswith("win"), "Linux sysfs paths (':' is not allowed in Windows names)")
    def test_dock_is_no_phone(self):
        """Lenovo dock: VIA Labs hubs + ThinkPad Lan (vendor 17ef) were shown as a phone (2026-11-20)."""
        import tempfile as tf
        from phonebackup import adbsetup

        def dev(root, name, vendor, maker, product, dev_class, ifaces):
            p = Path(root) / name
            p.mkdir()
            for k, v in (("idVendor", vendor), ("manufacturer", maker), ("product", product),
                         ("bDeviceClass", dev_class)):
                (p / k).write_text(v)
            for n, (c, sc) in enumerate(ifaces):
                i = Path(root) / f"{name}:1.{n}"
                i.mkdir()
                (i / "bInterfaceClass").write_text(c)
                (i / "bInterfaceSubClass").write_text(sc)
        with tf.TemporaryDirectory() as d:
            dev(d, "1-2", "17ef", "VIA Labs, Inc.", "USB2.0 Hub", "09", [("09", "00")])
            dev(d, "2-2.3", "17ef", "Lenovo", "ThinkPad Lan", "00", [("ff", "ff")])
            self.assertEqual(adbsetup._linux_usb_phones(d), [])
            dev(d, "3-1", "18d1", "Google", "Pixel 10 Pro", "00", [("06", "01")])          # MTP
            dev(d, "3-2", "17ef", "Lenovo", "Tab P12", "00", [("ff", "42")])               # ADB
            self.assertEqual(adbsetup._linux_usb_phones(d), ["Google Pixel 10 Pro", "Lenovo Tab P12"])


class LooseModelName(unittest.TestCase):
    def test_maker_in_front_is_probable_not_certain(self):
        from phonebackup import phoneid as P
        rec = P.Record(model="Pixel 10 Pro", serials=["TESTSERIAL0001"])
        self.assertEqual(P.compare(rec, P.PhoneId(model="Google Pixel 10 Pro")), P.PROBABLE)
        self.assertEqual(P.compare(rec, P.PhoneId(model="Pixel 10")), P.MISMATCH)        # another model
        self.assertEqual(P.compare(rec, P.PhoneId(model="Galaxy S25")), P.MISMATCH)


if __name__ == "__main__":
    unittest.main()
