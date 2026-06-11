from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebBackupDataScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "apps" / "web" / "index.html").read_text()
        cls.script = (ROOT / "apps" / "web" / "settings.js").read_text()
        cls.client = (ROOT / "apps" / "web" / "api-client.js").read_text()

    def test_backup_data_screen_shell_exists(self):
        required_ids = [
            "backup-view",
            "backup-create-form",
            "backup-type",
            "backup-include-media",
            "backup-include-token-metadata",
            "backup-history-list",
            "backup-export-actions",
            "backup-restore-form",
            "backup-restore-path",
            "backup-restore-preview",
            "backup-message",
            "backup-error",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', self.html)
        for copy in [
            "Backup & Data",
            "Create backup",
            "Restore preview",
            "Raw tokens are excluded",
            "No cloud upload",
        ]:
            self.assertIn(copy, self.html)

    def test_backup_data_screen_javascript_exists(self):
        for token in [
            '"backup"',
            "BACKUP_STORAGE_KEY",
            "function setupBackupData",
            "function renderBackupData",
            "function createBackup",
            "function previewRestore",
            "/api/backups",
            "/api/backups/restore-preview",
        ]:
            self.assertIn(token, self.script)
        self.assertIn("backupHistory", self.client)


if __name__ == "__main__":
    unittest.main()
