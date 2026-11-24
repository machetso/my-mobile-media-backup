"""Remove a backup from the list (user request 2026-11-23): gone at once, Undo until the program is
started again, then forgotten completely – also in the daily copies of the settings. The backup on
the drives stays. Settings in the test sandbox only."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phonebackup import backuplist, config, lastbackup  # noqa: E402

KEY = "Pixel 6 Pro - Karen"


def settings():
    return {"phones": {KEY: {"phone": "Pixel 6 Pro", "owner": "Karen", "when": "2026-01-01T10:00",
                             "status": "COMPLETED", "destinations": ["/x"], "folders": ["DCIM/Camera"],
                             "files": 1, "bytes": 1},
                       "Pixel 10 Pro - Karen": {"phone": "Pixel 10 Pro", "owner": "Karen", "when": "2026-11-01T10:00",
                                              "status": "COMPLETED", "destinations": ["/y"],
                                              "folders": ["DCIM/Camera"], "files": 1, "bytes": 1}},
            "backup_profiles": {KEY: {"destinations": ["/x"]}},
            "backup_history": {KEY: [{"kind": "backup"}]},
            "drive_state": {KEY: {"/x": {"missing": 0}}},
            "gfs_summary": {KEY: {}}}


class Remove(unittest.TestCase):
    def test_undo_then_forget_at_start(self):
        cfg = settings()
        config.save(cfg)
        lastbackup.mark_removed(cfg, [KEY])
        self.assertNotIn(KEY, [b["key"] for b in backuplist.known(cfg, {})])     # gone from the list
        self.assertNotIn("Pixel 6 Pro", [e["phone"] for e in lastbackup.phones(cfg)])
        lastbackup.undo_removed(cfg)
        self.assertIn(KEY, [b["key"] for b in backuplist.known(cfg, {})])        # back

        lastbackup.mark_removed(cfg, [KEY])
        copies = config.config_path().parent / "backups"
        copies.mkdir(parents=True, exist_ok=True)
        (copies / "config-2026-11-22.json").write_text(json.dumps(settings()), encoding="utf-8")
        self.assertEqual(lastbackup.purge_removed(cfg), [KEY])                  # the next start
        for section in lastbackup.PER_BACKUP:
            self.assertNotIn(KEY, cfg.get(section) or {})
        self.assertIn("Pixel 10 Pro - Karen", cfg["phones"])                      # the other one stays
        self.assertIn(KEY, cfg["phones_hidden"])                                # not found again on the drive
        self.assertNotIn(KEY, [b["key"] for b in backuplist.known(cfg, {KEY: ["/x/Karen/Pixel 6 Pro"]})])
        old = json.loads((copies / "config-2026-11-22.json").read_text(encoding="utf-8"))
        self.assertNotIn(KEY, old["phones"])                                    # also in the daily copy
        self.assertNotIn(KEY, old["backup_history"])
        self.assertEqual(lastbackup.purge_removed(cfg), [])                     # nothing left to do


class RemovedTheOldWay(unittest.TestCase):
    """User 2026-11-23: Alexandra's phone was removed before the change (only hidden) – its data
    stayed and "Secure backups" still offered it."""

    def test_hidden_with_data_is_forgotten_at_start(self):
        cfg = settings()
        cfg["phones"].pop(KEY)
        cfg["phones_hidden"] = [KEY]                       # the old "Remove from list"
        config.save(cfg)
        self.assertEqual(lastbackup.purge_removed(cfg), [KEY])
        self.assertNotIn(KEY, cfg["backup_profiles"])
        self.assertNotIn(KEY, cfg["drive_state"])
        self.assertIn(KEY, cfg["phones_hidden"])
        self.assertEqual(lastbackup.purge_removed(cfg), [])   # once
