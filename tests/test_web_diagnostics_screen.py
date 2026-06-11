from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebDiagnosticsScreenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "apps" / "web" / "index.html").read_text()
        cls.script = (ROOT / "apps" / "web" / "settings.js").read_text()
        cls.client = (ROOT / "apps" / "web" / "api-client.js").read_text()

    def test_diagnostics_screen_shell_exists(self):
        required_ids = [
            "diagnostics-view",
            "diagnostics-summary",
            "diagnostics-local-storage",
            "diagnostics-database",
            "diagnostics-ai",
            "diagnostics-integrations",
            "diagnostics-safety",
            "diagnostics-queue-jobs",
            "diagnostics-workflow",
            "diagnostics-backups",
            "diagnostics-recent-errors",
            "diagnostics-next-steps",
            "diagnostics-export-report",
            "diagnostics-copy-report",
            "diagnostics-message",
            "diagnostics-error",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', self.html)
        for copy in [
            "Diagnostics",
            "App Diagnostics",
            "Export diagnostic report",
            "Copy diagnostic summary",
            "What to do next",
            "No secrets",
        ]:
            self.assertIn(copy, self.html)

    def test_diagnostics_javascript_and_bootstrap_keys_exist(self):
        for token in [
            '"diagnostics"',
            "DIAGNOSTICS_STORAGE_KEY",
            "RECENT_ERRORS_STORAGE_KEY",
            "function setupDiagnostics",
            "function renderDiagnostics",
            "function exportDiagnosticReport",
            "function recordFriendlyError",
            "redactDiagnosticText",
            "/api/diagnostics",
            "/api/diagnostics/export",
        ]:
            self.assertIn(token, self.script)
        self.assertIn("diagnostics", self.client)
        self.assertIn("recentErrors", self.client)


if __name__ == "__main__":
    unittest.main()
