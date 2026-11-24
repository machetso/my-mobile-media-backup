"""Auto backup requirements (user request 2026-11-23): order, dependencies, hints."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phonebackup import autoready  # noqa: E402


class AutoReadyTest(unittest.TestCase):
    def test_order_and_all_done(self):
        r = autoready.requirements(True, True, True, True, True, True)
        self.assertEqual([x.id for x in r], ["backup", "drive", "paired", "allow", "wifi", "battery"])
        self.assertTrue(autoready.ready(r))
        self.assertTrue(all(x.hint.startswith("✓") for x in r))

    def test_later_steps_need_the_earlier_ones(self):
        r = {x.id: x for x in autoready.requirements(True, False, False, True, True, True)}
        self.assertFalse(r["drive"].ok)
        self.assertFalse(r["allow"].ok)                  # not paired: the phone setting does not count
        self.assertIn("Pair the phone app first", r["allow"].hint)
        self.assertFalse(r["wifi"].ok and r["wifi"].optional)
        self.assertFalse(r["battery"].ok)
        self.assertFalse(autoready.ready(list(r.values())))

    def test_battery_is_optional(self):
        r = autoready.requirements(True, True, True, True, True, False)
        self.assertTrue(autoready.ready(r))                    # the switch can be used
        bat = r[-1]
        self.assertTrue(bat.optional and not bat.ok)
        self.assertTrue(bat.hint.startswith("○ Battery: unrestricted (optional)"))
        self.assertIn("asks once per backup", bat.hint)

    def test_next_step_in_plain_words(self):
        r = autoready.requirements(True, False, False, False, False, False)
        self.assertIn("plug in your backup drive", autoready.next_step(r, False))
        r = autoready.requirements(True, True, True, False, False, False)
        self.assertIn("“Allow without asking”", autoready.next_step(r, False))
        r = autoready.requirements(True, True, True, True, False, False)
        self.assertTrue(autoready.ready(r))                     # no Wi-Fi needed: over the cable
        self.assertIn("switch “Auto backup” on", autoready.next_step(r, False))
        self.assertIn("“Trust the current Wi-Fi”", autoready.next_step(r, True))
        r = autoready.requirements(True, True, True, True, True, False)
        self.assertIn("switch “Auto backup” on", autoready.next_step(r, False))
        self.assertTrue(autoready.next_step(r, True).startswith("Tip:"))           # only the optional step
        self.assertEqual(autoready.next_step(autoready.requirements(*[True] * 6), True), "")

    def test_help_lists_every_step(self):
        h = autoready.help_text()
        for t in ("First backup made", "Backup drive connected", "Phone app paired",
                  "Allow without asking", "Trusted Wi-Fi on the phone", "Battery: unrestricted"):
            self.assertIn(t, h)


if __name__ == "__main__":
    unittest.main()
