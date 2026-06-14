from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.demo_day_check import run_demo_day_check
from scripts.local_beta_launcher import local_beta_readiness_check


ROOT = Path(__file__).resolve().parents[1]


class LocalBetaHardeningTests(unittest.TestCase):
    def test_local_beta_launcher_is_one_command_loopback_and_safe(self):
        readiness = local_beta_readiness_check(port=8044).to_dict()

        self.assertEqual(readiness["appName"], "Media Maxing")
        self.assertEqual(readiness["status"], "ready_for_local_beta")
        self.assertEqual(readiness["networkBoundary"], "loopback_only")
        self.assertEqual(readiness["controlCenterUrl"], "http://127.0.0.1:8044/#home")
        self.assertIn("python -m scripts.local_beta_launcher", readiness["command"])
        self.assertFalse(readiness["realPublishingEnabled"])
        self.assertFalse(readiness["realReplySendingEnabled"])
        self.assertFalse(readiness["realSocialApisEnabled"])

    def test_local_beta_launcher_cli_check_returns_safe_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.local_beta_launcher",
                "--check",
                "--json",
                "--port",
                "8044",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        serialized = json.dumps(payload).lower()
        self.assertEqual(payload["controlCenterUrl"], "http://127.0.0.1:8044/#home")
        self.assertFalse(payload["realPublishingEnabled"])
        self.assertNotIn("access_token", serialized)
        self.assertNotIn("refresh_token", serialized)
        self.assertNotIn("client_secret", serialized)

    def test_start_script_exists_for_non_coder_launch(self):
        script = ROOT / "start-media-maxing.bat"

        self.assertTrue(script.exists())
        self.assertIn(
            "python -m scripts.local_beta_launcher",
            script.read_text(encoding="utf-8"),
        )

    def test_demo_day_check_walks_daily_workflow_without_real_platform_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_demo_day_check(artifacts_dir=Path(temp_dir) / "artifacts")

        payload = result.to_dict()
        step_ids = {step["id"] for step in payload["steps"]}

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["controlCenterRoute"], "#home")
        self.assertFalse(payload["realPublishingEnabled"])
        self.assertFalse(payload["realReplySendingEnabled"])
        self.assertFalse(payload["realSocialApisEnabled"])
        self.assertTrue(
            {
                "onboarding",
                "media",
                "generate",
                "drafts",
                "calendar",
                "queue",
                "manual_export",
                "analytics",
                "engagement",
                "reply_suggestion",
                "learning",
                "backup",
                "diagnostics",
                "safety",
            }.issubset(step_ids)
        )


if __name__ == "__main__":
    unittest.main()
