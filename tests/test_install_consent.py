"""Nothing is installed on a phone without asking first (user request 2026-11-05)."""

import re
import unittest
from pathlib import Path

from phonebackup import companion

ROOT = Path(__file__).resolve().parent.parent


class InstallConsentTest(unittest.TestCase):
    def test_every_install_is_asked_first(self):
        guis = ("gui.py", "gui_backups.py")          # gui_backups: Settings → "Install / update over USB cable"
        for name in guis:
            src = (ROOT / "phonebackup" / name).read_text(encoding="utf-8")
            calls = [m.start() for m in re.finditer(r"\.install_companion\(", src)]
            self.assertTrue(calls, name)
            for pos in calls:
                before = src[max(0, pos - 2500):pos]
                self.assertIn("ui.ask_install(", before, f"install without asking first ({name})")
        gui = (ROOT / "phonebackup" / "gui.py").read_text(encoding="utf-8")
        self.assertIn('box.setDefaultButton(no)', gui)          # "No" is the default answer
        # the only exception (user decision 2026-11-10): the user chose "update automatically" for
        # exactly this phone (its serial) in that same question before
        self.assertIn('if src.serial in self.cfg.get("companion_auto", []):', gui)
        self.assertIn('lst = self.cfg.setdefault("companion_auto", [])', gui)
        self.assertEqual(gui.count('"companion_auto"'), 2)       # only: set in the question, read once
        # second exception (user request 2026-11-17): the button "Update phone app" (start page /
        # Overview) whose text and tooltip say what is installed – only from that button
        bk = (ROOT / "phonebackup" / "gui_backups.py").read_text(encoding="utf-8")
        self.assertIn("if not one_click:\n                title, text, details = g.install_question(", bk)
        self.assertEqual(re.findall(r"_install_app_cable\(one_click=True\)", gui + bk),
                         ["_install_app_cable(one_click=True)"])
        self.assertIn('box.button.setText(tr("Update phone app"))', bk)
        for f in (ROOT / "phonebackup").glob("*.py"):
            if f.name not in guis + ("sources.py",):
                self.assertNotIn("install_companion(", f.read_text(encoding="utf-8"), f.name)

    def test_question_explains_everything(self):
        for state in ("missing", "outdated", "no-permission"):
            title, text, details = companion.install_question(state, "Samsung SM-G780G", "RF8", "0.3.1",
                                                              1_600_000)
            self.assertIn("SM-G780G", text)
            self.assertIn(companion.APP_VERSION_NAME, text)
            for must in ("Why", ):
                self.assertIn(must, text)
            for must in ("1.6 MB", "WRITE_SECURE_SETTINGS", "nothing is downloaded", "Uninstall",
                         "cannot do", "back up without the app"):
                self.assertIn(must, details)
            # declining is always possible and the cable backup goes on without the app (user 2026-11-10)
            self.assertIn("Without the app", text)
            self.assertIn("works anyway", text)
        self.assertIn("0.3.1", companion.install_question("outdated", "P", "S", "0.3.1", 1)[1])

    def test_phone_app_has_the_program_version(self):
        """The phone app has the same version as the program (user request 2026-11-17): the
        Android build reads it from phonebackup/__init__.py with the same versionCode formula."""
        from phonebackup import __version__
        self.assertEqual(companion.APP_VERSION_NAME, __version__)
        gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
        self.assertIn('rootProject.file("../phonebackup/__init__.py")', gradle)
        self.assertIn("versionName = desktopVersion", gradle)
        self.assertIn("versionCode = desktopVersionCode", gradle)
        self.assertIn("a * 1000000 + b * 10000 + c * 100 + d", gradle)
        self.assertEqual(companion.version_code("0.9.8.4"), 90804)
        self.assertEqual(companion.version_code("1.0"), 1000000)
        self.assertGreater(companion.version_code("0.9.8.4"), 13)       # the last old-style code
        self.assertTrue(companion.app_outdated("0.9.0"))
        self.assertFalse(companion.app_outdated(__version__))
        self.assertFalse(companion.app_outdated(""))

    def test_paired_phone_found_by_name(self):
        cfg = {"companion_phones": [{"phone_id": "1", "name": "Pixel 10 Pro", "app_version": "0.9.0"},
                                    {"phone_id": "2", "name": "SM-G780G"}]}
        self.assertEqual(companion.paired_for(cfg, "Pixel 10 Pro")["phone_id"], "1")
        self.assertEqual(companion.paired_for(cfg, "Google Pixel 10 Pro")["phone_id"], "1")
        self.assertEqual(companion.paired_for(cfg, "Sam's phone", "SM-G780G")["phone_id"], "2")
        self.assertIsNone(companion.paired_for(cfg, "Galaxy A5"))


    def test_version_saved_after_an_update(self):
        """After updating, the start page must not still say "update" (user 2026-11-17): every
        install path sets the new version, and the phone app's own /info version wins."""
        gui = (ROOT / "phonebackup" / "gui.py").read_text(encoding="utf-8")
        bk = (ROOT / "phonebackup" / "gui_backups.py").read_text(encoding="utf-8")
        for src, name in ((gui, "gui.py"), (bk, "gui_backups.py")):
            for m in re.finditer(r"ok, msg = src\.install_companion\(apk\)", src):
                after = src[m.end():m.end() + 900]
                self.assertIn("src.companion_version = ", after, name)
                self.assertIn("src.companion_build_differs = False", after, name)   # 2026-11-17
        self.assertIn('version = getattr(link, "app_version", "") or getattr(src, "companion_version", "")', gui)
        comp = (ROOT / "phonebackup" / "companion.py").read_text(encoding="utf-8")
        self.assertIn('link.app_version = (info or {}).get("app_version", "")', comp)


    def test_old_copies_always_removed(self):
        """Never two copies of the phone app (user 2026-11-17: an old 0.7.0 under an earlier package
        name kept running and answered instead of 0.9.8.4): after EVERY install and on every new
        ADB connection old copies are removed – only packages that open phonebackup:// and are
        not the current app."""
        gui = (ROOT / "phonebackup" / "gui.py").read_text(encoding="utf-8")
        bk = (ROOT / "phonebackup" / "gui_backups.py").read_text(encoding="utf-8")
        for src, name in ((gui, "gui.py"), (bk, "gui_backups.py")):
            for m in re.finditer(r"ok, msg = src\.install_companion\(apk\)", src):
                self.assertIn("self._remove_old_app_copies(src)", src[m.end():m.end() + 1200], name)
        self.assertIn('step(tr("looking for old copies of the phone app"))\n'
                      '                self._remove_old_app_copies(src)', gui)
        from phonebackup import phoneguard
        self.assertEqual(phoneguard.old_copy_command("remove", "org.example.oldapp"), "pm uninstall org.example.oldapp")
        for bad in (phoneguard.COMPANION_PACKAGE, "com.android.settings; reboot", "", "x", "a.b c"):
            if bad == "com.android.settings; reboot" or bad in ("", "x", "a.b c", phoneguard.COMPANION_PACKAGE):
                with self.assertRaises(phoneguard.ForbiddenPhoneCommand, msg=bad):
                    phoneguard.old_copy_command("remove", bad)
        with self.assertRaises(phoneguard.ForbiddenPhoneCommand):
            phoneguard.old_copy_command("clear", "org.example.oldapp")

    def test_remove_only_listed_old_copies(self):
        from unittest import mock
        from phonebackup import phoneguard
        from phonebackup.sources import AdbSource
        src = AdbSource.__new__(AdbSource)
        src.adb, src.serial = "adb", "x"
        listing = ("2 activities found:\n  Activity #0:\n    org.example.oldapp/.MainActivity\n"
                   "  Activity #1:\n    %s/.MainActivity\n" % phoneguard.COMPANION_PACKAGE)
        src.control = lambda name, timeout=30: (0, listing)
        ran = []

        def run(cmd, timeout=0):
            ran.append(cmd[-1])
            out = b"versionName=0.7.0\n" if cmd[-1].startswith("dumpsys") else b"Success\n"
            return mock.Mock(returncode=0, stdout=out, stderr=b"")
        with mock.patch("phonebackup.sources._run", run):
            self.assertEqual(src.old_companion_copies(), [("org.example.oldapp", "0.7.0")])
            with self.assertRaises(phoneguard.ForbiddenPhoneCommand):
                src.remove_old_companion("com.android.settings")       # not listed → refused
            with self.assertRaises(phoneguard.ForbiddenPhoneCommand):
                src.remove_old_companion(phoneguard.COMPANION_PACKAGE)  # never the current app
            self.assertEqual(src.remove_old_companion("org.example.oldapp")[0], True)
        self.assertIn("pm uninstall org.example.oldapp", ran)
        self.assertFalse([c for c in ran if "uninstall" in c and "oldapp" not in c])


    def test_same_version_other_build_is_outdated(self):
        """The phone app has the program's version, so two builds can share it (user 2026-11-17:
        an earlier 0.9.8.4 build was not shown as outdated) – the app file is compared too."""
        from phonebackup import phoneguard
        from phonebackup.sources import AdbSource
        src = AdbSource.__new__(AdbSource)
        src.adb, src.serial = "adb", "x"
        dump = ("versionCode=%d\n versionName=%s\n android.permission.WRITE_SECURE_SETTINGS: granted=true\n"
                % (companion.APP_VERSION_CODE, companion.APP_VERSION_NAME))
        src.control = lambda name, timeout=30: (
            0, f"package:{phoneguard.COMPANION_PACKAGE}" if name == "companion_installed" else dump)
        for same, expected in ((False, "outdated"), (True, "ready"), (None, "ready")):
            src.companion_check = lambda apk, same=same: (True, same)
            self.assertEqual(src.companion_state("bundled.apk"), expected, same)
            self.assertEqual(src.companion_build_differs, same is False)
        self.assertEqual(src.companion_state(), "ready")          # no file given: version only
        _t, text, _d = companion.install_question("outdated", "P", "S", companion.APP_VERSION_NAME, 1)
        self.assertIn("older build", text)


if __name__ == "__main__":
    unittest.main()
