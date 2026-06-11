import tempfile
import unittest
from pathlib import Path

from scripts.db.brand_profiles import list_brand_profiles
from scripts.db.init_db import initialize_database
from scripts.db.settings import load_app_settings
from scripts.services.onboarding import (
    OnboardingService,
    ONBOARDING_STEP_IDS,
    SETUP_CHECKLIST_ITEM_IDS,
)


class OnboardingServiceTest(unittest.TestCase):
    def test_fresh_database_starts_onboarding_with_checklist(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.sqlite"
            initialize_database(db_path)

            state = OnboardingService(db_path).get_state()

            self.assertEqual(state.status, "not_started")
            self.assertEqual(state.currentStep, "welcome")
            self.assertEqual([step["id"] for step in state.steps], ONBOARDING_STEP_IDS)
            self.assertEqual(
                [item["id"] for item in state.checklist],
                SETUP_CHECKLIST_ITEM_IDS,
            )
            self.assertEqual(
                state.checklistById["local_data_ready"]["status"],
                "completed",
            )
            self.assertEqual(
                state.checklistById["brand_profile_created"]["status"],
                "not_started",
            )

    def test_complete_onboarding_creates_brand_profile_and_safe_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.sqlite"
            initialize_database(db_path)

            result = OnboardingService(db_path).complete(
                {
                    "brandProfile": {
                        "businessName": "Owner Roof Care",
                        "industry": "Roof cleaning",
                        "description": "Local exterior care business.",
                        "services": ["roof cleaning", "gutter cleaning"],
                        "serviceAreas": ["Demo City", "North County"],
                        "brandVoice": "Friendly, plain-spoken, careful.",
                        "commonCTAs": ["Request an estimate"],
                        "website": "https://example.local",
                        "phone": "555-0199",
                        "email": "hello@example.local",
                    },
                    "settings": {
                        "localDataDirectory": "./data",
                        "defaultPlatformTargets": ["instagram", "facebook", "linkedin"],
                        "requireApprovalBeforePublishing": True,
                        "requireApprovalBeforeReplying": True,
                        "emergencyPauseEnabled": False,
                        "automationLevel": "approval_queue",
                    },
                    "completedSteps": [
                        "welcome",
                        "local_data",
                        "brand_profile",
                        "business_details",
                        "services_areas",
                        "platforms",
                        "safety",
                        "media",
                        "demo_draft",
                        "next_steps",
                    ],
                    "skippedSteps": ["media", "demo_draft"],
                }
            )

            settings = load_app_settings(db_path)
            profiles = list_brand_profiles(db_path)

            self.assertEqual(result.status, "completed")
            self.assertIsNotNone(result.completedAt)
            self.assertEqual(settings.defaultPlatformTargets, ["instagram", "facebook", "linkedin"])
            self.assertEqual(settings.automationLevel, "approval_queue")
            self.assertTrue(settings.requireApprovalBeforePublishing)
            self.assertTrue(settings.requireApprovalBeforeReplying)
            self.assertFalse(settings.emergencyPauseEnabled)
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0].businessName, "Owner Roof Care")
            self.assertEqual(profiles[0].services, ["roof cleaning", "gutter cleaning"])
            self.assertEqual(
                result.checklistById["brand_profile_created"]["status"],
                "completed",
            )
            self.assertEqual(
                result.checklistById["safety_settings_confirmed"]["status"],
                "completed",
            )

    def test_skip_and_restart_onboarding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.sqlite"
            initialize_database(db_path)
            service = OnboardingService(db_path)

            skipped = service.skip(reason="Owner wants to explore first.")
            restarted = service.restart()

            self.assertEqual(skipped.status, "skipped")
            self.assertEqual(restarted.status, "in_progress")
            self.assertEqual(restarted.currentStep, "welcome")
            self.assertEqual(restarted.skippedSteps, [])


if __name__ == "__main__":
    unittest.main()
