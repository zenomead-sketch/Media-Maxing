from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_INDEX = REPO_ROOT / "apps" / "web" / "index.html"
WEB_SCRIPT = REPO_ROOT / "apps" / "web" / "settings.js"
API_CLIENT = REPO_ROOT / "apps" / "web" / "api-client.js"


class WebOnboardingScreenTest(unittest.TestCase):
    def setUp(self):
        self.html = WEB_INDEX.read_text(encoding="utf-8")
        self.script = WEB_SCRIPT.read_text(encoding="utf-8")
        self.api_client = API_CLIENT.read_text(encoding="utf-8")

    def test_onboarding_route_has_required_steps_and_safety_copy(self):
        required_ids = [
            "onboarding-view",
            "onboarding-progress",
            "onboarding-step-title",
            "onboarding-local-data-directory",
            "onboarding-brand-form",
            "onboarding-platforms",
            "onboarding-safety-summary",
            "onboarding-media-skip",
            "onboarding-demo-draft",
            "onboarding-complete",
            "onboarding-skip",
            "onboarding-error",
            "onboarding-success",
        ]
        for element_id in required_ids:
            self.assertIn(f'id="{element_id}"', self.html)

        for copy in (
            "Nothing publishes without approval",
            "Real social connections can be configured later",
            "Mock/demo mode is available",
            "Real publishing: locked by default",
            "Real auto-replies: disabled",
        ):
            self.assertIn(copy, self.html)

    def test_home_setup_checklist_and_settings_restart_are_present(self):
        for element_id in (
            "home-setup-checklist",
            "home-onboarding-start",
            "settings-restart-onboarding",
        ):
            self.assertIn(f'id="{element_id}"', self.html)

        self.assertIn("Brand profile created", self.html)
        self.assertIn("Manual export tested", self.html)

    def test_onboarding_script_uses_api_and_local_fallback(self):
        for token in (
            '"onboarding"',
            "ONBOARDING_STORAGE_KEY",
            "function setupOnboarding",
            "function renderSetupChecklist",
            "function completeOnboarding",
            "function skipOnboarding",
            "/api/onboarding/complete",
            "/api/onboarding/skip",
            "/api/onboarding/restart",
        ):
            self.assertIn(token, self.script)

        self.assertIn("onboarding", self.api_client)


if __name__ == "__main__":
    unittest.main()
