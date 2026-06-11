from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX = REPO_ROOT / "apps" / "web" / "index.html"
WEB_SCRIPT = REPO_ROOT / "apps" / "web" / "settings.js"
API_CLIENT = REPO_ROOT / "apps" / "web" / "api-client.js"


class WebSafetyCenterScreenTest(unittest.TestCase):
    def setUp(self):
        self.html = WEB_INDEX.read_text(encoding="utf-8")
        self.script = WEB_SCRIPT.read_text(encoding="utf-8")
        self.api_client = API_CLIENT.read_text(encoding="utf-8")

    def test_safety_center_route_has_required_sections(self):
        for element_id in (
            "safety-view",
            "safety-emergency-toggle",
            "safety-automation-level",
            "safety-publishing-status",
            "safety-reply-status",
            "safety-queue-status",
            "safety-connected-status",
            "safety-critical-flags",
            "safety-pending-approvals",
            "safety-kill-switch",
            "safety-audit-log",
            "safety-export-report",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

        for copy in (
            "Emergency pause",
            "Real publishing remains disabled",
            "Replies are not sent automatically",
            "Dangerous actions require confirmation",
            "What pause blocks",
            "What remains allowed",
        ):
            self.assertIn(copy, self.html)

    def test_safety_center_script_wires_api_and_local_fallback(self):
        for token in (
            '"safety"',
            "SAFETY_CENTER_STORAGE_KEY",
            "function setupSafetyCenter",
            "function renderSafetyCenter",
            "function toggleEmergencyPause",
            "function runKillSwitchAction",
            "/api/safety-center/emergency-pause",
            "/api/safety-center/kill-switch/",
        ):
            self.assertIn(token, self.script)

        self.assertIn("safetyCenter", self.api_client)


if __name__ == "__main__":
    unittest.main()
