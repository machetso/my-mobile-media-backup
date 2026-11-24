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

    def test_auto_backup_switch(self):
        """Auto backup (user request 2026-11-23): greyed until every requirement is done; the automatic
        backup only goes into a backup whose switch is on."""
        w, gui = self.w, self.gui
        key = "Pixel 10 Pro - Karen"
        w._update_home()
        row = w._phone_widgets[key].auto
        self.assertFalse(row.switch.isEnabled())                       # no phone app paired yet
        self.assertEqual(len(row.bar.blocks), 6)
        self.assertIn("✗ Phone app paired", row.bar.blocks[2].toolTip())
        self.assertIn("✓ First backup made", row.bar.blocks[0].toolTip())
        w.cfg["phone_modes"] = {"Pixel 10 Pro": {"a": True, "w": 1, "b": False}}   # battery optional
        with mock.patch.object(gui, "paired_for", lambda cfg, *n: {"name": "Pixel 10 Pro"}):
            w._update_home()
            self.assertTrue(row.switch.isEnabled())
            self.assertIsNone(w._auto_target("Pixel 10 Pro"))         # switch still off
            row.switch.click()
            self.assertTrue(w.cfg["backup_profiles"][key]["auto"])
            self.assertEqual(w._auto_target("Pixel 10 Pro"), key)

    def test_phone_checks_in(self):
        """Battery-saving requests (2026-11-23): the phone checks in; a backup is wanted only with Auto
        backup on (once an hour) or after "Update backup" was clicked while it was away."""
        from types import SimpleNamespace
        w = self.w
        key = "Pixel 10 Pro - Karen"
        h = SimpleNamespace(name="Pixel 10 Pro", mode="auto", homes=1, unrestricted=True, time=time.time())
        self.assertFalse(w._hello_decide(h))                              # Auto backup off, nothing clicked
        w._wanted[key] = time.time()                                      # "Update backup" while away
        self.assertTrue(w._hello_decide(h))
        self.assertEqual(w._auto_pending["key"], key)
        w._on_hello(h)
        self.assertNotIn(key, w._wanted)
        self.assertEqual(w.cfg["phone_modes"]["Pixel 10 Pro"], {"a": True, "w": 1, "b": True})
        w._auto_pending = None
        w.cfg.setdefault("backup_profiles", {}).setdefault(key, {})["auto"] = True
        self.assertTrue(w._hello_decide(h))                               # Auto backup on and due
        self.assertNotIn("key", w._auto_pending)
        w._update_home()
        w._fill_phone_rows()
        self.assertIn("checked in", w._phone_widgets[key].nearby.text())

    def test_mtp_count_from_saved_list_then_checked(self):
        """MTP without the phone app (user request 2026-11-23): the count comes at once from the phone's
        saved file list, then the real list is read; a difference is announced on the phone's row."""
        from types import SimpleNamespace
        from phonebackup import knownlist
        w = self.w
        key = "Pixel 10 Pro - Karen"
        blob = knownlist.pack([knownlist.digest("DCIM/Camera/1.jpg", 10)])
        knownlist._save(key, "2026-11-23 13:00:00", "/x", blob)
        knownlist.save_phone(key, [("DCIM/Camera/1.jpg", 10)], ["DCIM/Camera"])
        files = [SimpleNamespace(rel="DCIM/Camera/1.jpg", size=10), SimpleNamespace(rel="DCIM/Camera/2.mp4", size=5)]
        src = SimpleNamespace(device_name="Pixel 10 Pro", list_files=lambda folders: (files, []))
        w.source = src
        said = []
        w.bridge.list_changed.connect(lambda k, t: said.append((k, t)))
        w._count_here_job(src)
        self.app.processEvents()
        self.assertEqual(w._new_counts[key], (0, 1, 5))
        self.assertEqual(len(said), 1)
        self.assertIn("Checked with the phone", said[0][1])
        self.assertIn("1 video", said[0][1])
        self.assertEqual(knownlist.load_phone(key, ["DCIM/Camera"]), [("DCIM/Camera/1.jpg", 10), ("DCIM/Camera/2.mp4", 5)])
        w.source = None

    def test_missing_drives_said_not_searched(self):
        """Drives of the last backup not there (VeraCrypt volumes closed, user report 2026-11-23): the
        start screen says so, and "Update backup" names the drives – no search for other folders."""
        w, gui = self.w, self.gui
        e = w.cfg["phones"]["Pixel 10 Pro - Karen"]
        e["destinations"] = ["/media/veracrypt-test-absent/2nd Backup/MMMB_Vol.1"]   # never there
        w._update_home()
        row = w._phone_widgets["Pixel 10 Pro - Karen"]
        self.assertFalse(row.nodrive.isHidden())
        self.assertIn("Backup drives not available", row.nodrive.text())
        shown = []
        with mock.patch.object(gui.MainWindow, "_connected_phone", lambda s: "Pixel 10 Pro"), \
                mock.patch.object(gui, "detect_unmounted", lambda: []), \
                mock.patch.object(gui.MainWindow, "_show_missing_drives", lambda s, k, d=None: shown.append((k, d))):
            got = w._update_ready("Pixel 10 Pro - Karen", e, "Pixel 10 Pro", "Karen", list(e["destinations"]))
        self.assertIsNone(got)
        self.assertEqual(shown, [("Pixel 10 Pro - Karen", ["/media/veracrypt-test-absent/2nd Backup/MMMB_Vol.1"])])
        from phonebackup import findbackup
        self.assertFalse(hasattr(findbackup, "search"))     # the search by names is gone
        e["destinations"] = [os.path.join(self.tmp.name, "Backup Disk")]
        w._update_home()
        self.assertTrue(row.nodrive.isHidden())

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
                               lambda cfg, e, a, since, folders, ready, known=("", ""): asked.append((since, folders, ready)) or (23, 4, 1610612736)):
            w._count_new([f])
        self.assertEqual(asked, [(1_790_000_000, ["DCIM/Camera"], "")])         # drive there: ready
        self.assertEqual(f["new"], (23, 4, 1610612736))
        w._nearby = [f]
        w._update_home()
        w._show_nearby()
        row = w._phone_widgets["Pixel 10 Pro - Karen"]
        self.assertIn("23 photos and 4 videos (1.5 GB) not backed up yet", row.nearby.text())
        # only in "Your phones", not again in the nearby box (user request 2026-11-23)
        self.assertNotIn("23 photos and 4 videos", w.nearby_label.text())
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


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class AfterBackupTest(unittest.TestCase):
    """User 2026-11-23: after a complete backup the phone's row still said "6 photos … not backed up
    yet" and the bottom line stayed "Backup: COMPLETED …" – the phone is not asked again afterwards."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_count_reset_and_bottom_line_cleared(self):
        w = self.w
        key = "Pixel 10 Pro - Karen"
        w._new_counts[key] = (6, 0, None)
        w._running_backup = ("Pixel 10 Pro", "Karen", ["DCIM/Camera"], w.cfg["phones"][key]["destinations"])
        w.source = None
        with mock.patch.object(self.gui.QMessageBox, "exec", lambda box: 0):
            w._backup_done(("COMPLETED", [], [], "EVERYTHING COPIED CORRECTLY"))
        self.assertEqual(w._new_counts[key], (0, 0, 0))
        self.assertEqual(w._counts_text(w._new_counts[key]), "everything is backed up")
        self.assertEqual(w.progress_label.text(), "")

    def test_other_folders_once_do_not_reset(self):
        w = self.w
        key = "Pixel 10 Pro - Karen"
        w._new_counts[key] = (6, 0, None)
        w._running_backup = ("Pixel 10 Pro", "Karen", ["Download"], w.cfg["phones"][key]["destinations"])
        w.source = None
        with mock.patch.object(self.gui.QMessageBox, "exec", lambda box: 0):
            w._backup_done(("COMPLETED", [], [], "EVERYTHING COPIED CORRECTLY"))
        self.assertEqual(w._new_counts[key], (6, 0, None))


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class HistoryMarkTest(unittest.TestCase):
    """The date marks the entries up to and including it, at once (user 2026-11-23)."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_mark_follows_the_date(self):
        w = self.w
        key = "Pixel 10 Pro - Karen"
        w.cfg["backup_history"] = {key: [
            {"kind": "backup", "when": f"2026-11-{d:02d}T10:00:00", "files": 1, "bytes": 1, "status": "COMPLETED",
             "drives": []} for d in (1, 10, 20)]}
        w._refresh_backups()
        w._fill_backup_history()
        self.assertFalse(w.history_delete_btn.isEnabled())                 # no date yet: nothing marked
        w.history_until.set_day("2026-11-10")
        self.assertEqual(w.history_delete_btn.text(), "Delete 2 marked entries")
        w.history_until.set_day("2026-11-25")
        self.assertEqual(w.history_delete_btn.text(), "Delete 3 marked entries")
        w.history_until.set_day("2026-11-10")
        with mock.patch.object(self.gui.QMessageBox, "question", lambda *a, **k: self.gui.QMessageBox.Yes):
            w._delete_marked_history()
        self.assertEqual(w.backup_history.topLevelItemCount(), 1)
        self.assertEqual(w.backup_history.topLevelItem(0).text(0), "2026-11-20 10:00")
        self.assertEqual(w.history_until.marked, {"2026-11-20"})          # the dots in the calendar
        self.assertEqual(w.history_until.text(), "choose a date")
        self.assertTrue(w.history_undo_btn.isEnabled())
        w._undo_history_delete()                                            # the 2 entries are back
        self.assertEqual(w.backup_history.topLevelItemCount(), 3)
        self.assertFalse(w.history_undo_btn.isEnabled())


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class StartScreenTextTest(unittest.TestCase):
    """User 2026-11-23: less text; the install hint only when the app cannot be seen on a nearby phone."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_short_texts(self):
        w = self.w
        self.assertEqual(w._no_phone_text(), "Recommended: connect USB cable – fastest and most reliable.")
        w._nearby = [dict(self.near)]                    # the phone app answers on a nearby phone
        w._show_nearby()
        text = w.nearby_label.text()
        self.assertIn("<b>Karen&#x27;s Pixel 10 Pro is nearby</b>", text)
        self.assertIn("Allow connection on the phone app.", text)
        self.assertNotIn("Recommended", text)


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class NearbyAtStartTest(unittest.TestCase):
    """User 2026-11-23: while the first search for nearby phones runs, only the red box says
    "Looking for a phone …"; the yellow box appears only when a phone was found. presence.scan is
    simulated – no real phones."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_looking_in_the_red_box_then_result(self):
        import threading
        from phonebackup import presence
        w = self.w
        go = threading.Event()

        def slow_scan(cfg):
            go.wait(5)
            return []
        with mock.patch.dict(os.environ, {"PHONEBACKUP_NO_PRESENCE": ""}), \
                mock.patch.object(presence, "scan", slow_scan):
            os.environ.pop("PHONEBACKUP_NO_PRESENCE", None)
            w.source = None
            w._presence_first_done = False
            w._set_phone_status(w._no_phone_text(), self.gui.GRAY)
            w._presence_tick()
            self.assertEqual(w._last_status[0], "Looking for a phone …")
            self.assertFalse(w.nearby_box.isHidden())              # the moving line at the same time …
            self.assertTrue(w.nearby_label.isHidden())             # … without any text
            self.assertTrue(w.nearby_btn.isHidden())
            go.set()
            for _ in range(100):
                if getattr(w, "_presence_first_done", False):
                    break
                time.sleep(0.02)
            w._show_nearby()
            self.assertEqual(w._last_status[0], w._no_phone_text())  # search done: the normal line
            self.assertTrue(w.nearby_box.isHidden())                 # nothing found: no yellow box


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class AutoAskTest(unittest.TestCase):
    """User 2026-11-23: the phone app nearby and no USB debugging → the computer asks the phone for
    the connection by itself, once each time it comes near. send_ask is simulated."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_asked_once_per_arrival(self):
        w = self.w
        sent = []
        with mock.patch.object(self.gui.presence, "send_ask", lambda cfg, e, a, **k: sent.append(a) or "asked"):
            w.source = None
            near = dict(self.near, self=False)
            w._auto_ask_nearby([near])
            w._auto_ask_nearby([near])                     # still near: not again
            for _ in range(50):
                if sent:
                    break
                time.sleep(0.02)
            self.assertEqual(sent, ["192.0.2.9:47825"])
            w._auto_ask_nearby([])                         # gone …
            w._auto_ask_nearby([near])                     # … and back: asked again
            for _ in range(50):
                if len(sent) == 2:
                    break
                time.sleep(0.02)
            self.assertEqual(len(sent), 2)
            w.source = object()                            # connected: nothing is asked
            w._auto_ask_nearby([])
            w._auto_ask_nearby([near])
            time.sleep(0.1)
            self.assertEqual(len(sent), 2)
            w.source = None


@unittest.skipUnless(HAVE_QT, "PySide6 not installed")
class ConnectedSubtitleTest(unittest.TestCase):
    """User 2026-11-23 (third time): below the headline of a connection ONLY what connection it is
    and whether the transfer is verified – whatever text the program passes."""
    setUp = OneClickTest.setUp
    tearDown = OneClickTest.tearDown

    def test_only_connection_and_verified(self):
        from phonebackup.sources import AdbSource
        from phonebackup.companion import CompanionSource
        w = self.w
        adb = AdbSource.__new__(AdbSource)
        adb.device_name, adb.manufacturer, adb.serial = "Pixel 10 Pro", "Google", "PX10TEST000001"
        app = CompanionSource.__new__(CompanionSource)
        app.device_name, app.manufacturer, app.app_version, app.entry = "Pixel 10 Pro", "Google", "0.9.9.0", {}
        try:
            for src, want in ((adb, "Connected via ADB (verified data transfer)"),
                              (app, "Connected via the phone app's TLS connection (verified data transfer)")):
                w.source = src
                w._set_phone_status("Connected via ADB and verified: Google Pixel 10 Pro (Android 17) – "
                                    "the phone's key matches … Fast mode with hash check.", self.gui.GREEN)
                import html
                self.assertEqual(html.unescape(w.home_status.detail.text()), want)
                self.assertTrue(w.home_status.hint.isHidden())
        finally:
            w.source = None
