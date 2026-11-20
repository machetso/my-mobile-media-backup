"""One click on "Update backup" while the phone is only nearby (user request 2026-11-20): the phone is
asked to open backup mode (no window on the computer), the backup starts when it is connected, and
"how many photos and videos are new?" is shown on the phone's row. No real phone, network or settings."""
import os
import tempfile
import time
import unittest
from unittest import mock

try:
    import PySide6  # noqa: F401
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class OneClickTest(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name, "APPDATA": self.tmp.name,
                                                "PHONEBACKUP_NO_PRESENCE": "1", "HOME": self.tmp.name})
        self.env.start()
        from PySide6.QtWidgets import QApplication
        from phonebackup import gui
        self.gui = gui
        self.app = QApplication.instance() or QApplication([])
        self.patches = [mock.patch.object(gui.MainWindow, "_adb_poller", lambda s: None),
                        mock.patch.object(gui, "find_adb", lambda cfg: None)]
        for p in self.patches:
            p.start()
        self.w = gui.MainWindow()
        drive = os.path.join(self.tmp.name, "Backup Disk")
        os.makedirs(drive)
        self.w.cfg["phones"] = {"Pixel 10 Pro - Karen": {
            "phone": "Pixel 10 Pro", "model": "Pixel 10 Pro", "owner": "Karen", "folders": ["DCIM/Camera"],
            "destinations": [drive], "when": "2026-11-19T10:00", "since": 1_790_000_000,
            "files": 1, "bytes": 1, "status": "COMPLETED"}}
        self.near = {"name": "Pixel 10 Pro", "how": "app", "ask": "192.0.2.9:47825", "auto": True, "self": False,
                     "entry": {"name": "Pixel 10 Pro", "secret": "ab" * 32}}

    def tearDown(self):
        self.w._stop.set()
        self.w.close()
        for p in self.patches:
            p.stop()
        self.env.stop()
        self.tmp.cleanup()

    def _wait(self, cond):
        for _ in range(100):
            if cond():
                return
            time.sleep(0.02)
        self.fail("timed out")

    def test_click_opens_the_phone_without_a_window(self):
        w, gui = self.w, self.gui
        w._nearby = [self.near]
        sent = []
        with mock.patch.object(gui.presence, "send_ask", lambda cfg, e, a, auto=False: sent.append(auto) or "started"), \
                mock.patch.object(gui.QMessageBox, "exec", side_effect=AssertionError("no window expected")):
            w._update_latest("Pixel 10 Pro - Karen")
            self._wait(lambda: w._auto_pending is not None)
        self.assertEqual(sent, [True])
        self.assertEqual(w._auto_pending["key"], "Pixel 10 Pro - Karen")

    def test_ask_me_falls_back_to_the_tap_on_the_phone(self):
        w, gui = self.w, self.gui
        w._nearby = [dict(self.near, auto=False)]
        sent = []

        def ask(cfg, e, a, auto=False):
            sent.append(auto)
            return "not_auto" if auto else "asked"
        with mock.patch.object(gui.presence, "send_ask", ask):
            w._update_latest("Pixel 10 Pro - Karen")
            self._wait(lambda: w._auto_pending is not None)
        self.assertEqual(sent, [True, False])
        self.assertIn("Allow", w._nearby_info)

    def test_no_answer_is_short_with_the_way_out(self):
        """User 2026-11-20: no "urlopen error …" on the screen – short, with the solution."""
        w, gui = self.w, self.gui
        w._nearby = [self.near]

        def ask(cfg, e, a, auto=False):
            raise OSError("<urlopen error timed out>")
        with mock.patch.object(gui.presence, "send_ask", ask):
            w._update_latest("Pixel 10 Pro - Karen")
            self._wait(lambda: "answer" in w._nearby_info)
        self.assertNotIn("urlopen", w._nearby_info)
        self.assertIn("USB cable", w._nearby_info)
        self.assertIn("VPN", w._nearby_info)          # the usual cause (2026-11-20)

    def test_new_photos_are_counted_and_shown(self):
        w, gui = self.w, self.gui
        f = dict(self.near)
        asked = []
        with mock.patch.object(gui.presence, "ask_new",
                               lambda cfg, e, a, since, folders, ready: asked.append((since, folders, ready)) or (23, 4, 1610612736)):
            w._count_new([f])
        self.assertEqual(asked, [(1_790_000_000, ["DCIM/Camera"], "")])         # drive there: ready
        self.assertEqual(f["new"], (23, 4, 1610612736))
        w._nearby = [f]
        w._update_home()
        w._show_nearby()
        row = w._phone_widgets["Pixel 10 Pro - Karen"]
        self.assertIn("23 photos and 4 videos (1.5 GB) not backed up yet", row.nearby.text())
        self.assertIn("23 photos and 4 videos (1.5 GB)", w.nearby_label.text())
        self.assertNotIn("#5a5a5a", row.button.styleSheet())                   # can start: not grey

    def test_grey_button_and_what_the_phone_is_told(self):
        w = self.w
        w._update_home()
        w._show_nearby()                          # phone neither connected nor nearby
        row = w._phone_widgets["Pixel 10 Pro - Karen"]
        self.assertIn("#5a5a5a", row.button.styleSheet())
        w.cfg["phones"]["Pixel 10 Pro - Karen"]["destinations"] = [os.path.join(self.tmp.name, "gone")]
        with mock.patch.object(self.gui, "detect_unmounted", lambda: []):
            self.assertEqual(w._phone_news("Pixel 10 Pro")[3], "no_drive")
        self.assertEqual(w._phone_news("Galaxy A55")[3], "no_backup")

    def test_back_up_now_on_the_phone_starts_here(self):
        """The phone app says "want" (its tap time) in its answer to /status: one click here, once."""
        w, gui = self.w, self.gui

        class Client:
            def request(self, method, path, body=None):
                return {"photos": 3, "videos": 1, "bytes": 336_592_896, "want": 1_790_000_123}
        src = mock.MagicMock(spec=gui.CompanionSource)
        src.client = Client()
        src.device_name = "Pixel 10 Pro"
        started = []
        w._update_latest = lambda key, folders_once=None: started.append((key, w._one_click))
        w.source = src
        got = []
        w.bridge.phone_wants.connect(lambda: got.append(1))
        w._status_to_phone(src)
        w._status_to_phone(src)                   # the same tap again: not twice
        self.app.processEvents()
        self.assertEqual(got, [1])
        self.assertEqual(w._new_counts["Pixel 10 Pro - Karen"], (3, 1, 336_592_896))
        self.assertIn("(321 MB)", w._counts_text(w._new_counts["Pixel 10 Pro - Karen"]))
        self.assertEqual(started, [("Pixel 10 Pro - Karen", True)])
        w.source = None


class SizeTextTest(unittest.TestCase):
    def test_not_more_detailed(self):
        from phonebackup import ui
        self.assertEqual(ui.short_size(1610612736), "1.5 GB")
        self.assertEqual(ui.short_size(336_592_896), "321 MB")
        self.assertEqual(ui.short_size(200_000), "under 1 MB")

    def test_older_phone_app_without_size(self):
        from phonebackup import presence
        self.assertEqual(presence.counts_of({"photos": 2, "videos": 0}), (2, 0, None))


if __name__ == "__main__":
    unittest.main()
