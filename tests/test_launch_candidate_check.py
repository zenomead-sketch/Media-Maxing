from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class LaunchCandidateCheckTests(unittest.TestCase):
    def test_launch_check_module_reports_required_sections(self) -> None:
        from scripts.launch_check import REQUIRED_CHECKLIST_SECTIONS, run_launch_check

        required = {
            "Install and setup",
            "Environment variables",
            "Database and seed",
            "Onboarding",
            "Brand Brain",
            "Media Library",
            "Generate",
            "Drafts and approvals",
            "Calendar",
            "Publish Queue",
            "Manual Export",
            "Connected Accounts mock mode",
            "Setup Wizard",
            "Analytics",
            "Engagement Inbox",
            "Reply suggestions",
            "AI learning loop",
            "Weekly reports",
            "Safety Center",
            "Emergency pause",
            "Backup and restore preview",
            "Diagnostics",
            "Desktop packaging",
            "Documentation",
            "Security scan",
            "Final build",
        }
        self.assertTrue(required.issubset(set(REQUIRED_CHECKLIST_SECTIONS)))

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = run_launch_check(
                database_path=Path(tmp_dir) / "launch-check.sqlite",
                artifacts_dir=Path(tmp_dir) / "artifacts",
                repo_root=REPO_ROOT,
                run_tests=False,
                run_compile=False,
                run_node_checks=False,
            )

        self.assertIn(result.status, {"pass", "partial", "fail"})
        self.assertEqual(result.checks["database_and_seed"].status, "pass")
        self.assertEqual(result.checks["security_scan"].status, "pass")
        self.assertIn("real publishing", result.safety_summary.lower())
        self.assertFalse(result.security_scan.actual_secret_like_values)

    def test_launch_check_cli_outputs_json_without_printing_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            command = [
                sys.executable,
                "-m",
                "scripts.launch_check",
                "--database",
                str(Path(tmp_dir) / "launch-cli.sqlite"),
                "--artifacts-dir",
                str(Path(tmp_dir) / "artifacts"),
                "--skip-tests",
                "--skip-compile",
                "--skip-node-checks",
                "--json",
            ]
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("must-not-leak", completed.stdout.lower())
        payload = json.loads(completed.stdout)
        self.assertIn(payload["status"], {"pass", "partial", "fail"})
        self.assertEqual(payload["checks"]["database_and_seed"]["status"], "pass")
        self.assertEqual(payload["checks"]["security_scan"]["status"], "pass")

    def test_launch_candidate_checklist_doc_covers_core_and_safety_workflows(self) -> None:
        doc_path = REPO_ROOT / "docs" / "launch-candidate-checklist.md"
        self.assertTrue(doc_path.exists(), "docs/launch-candidate-checklist.md is required")
        text = doc_path.read_text(encoding="utf-8")
        for heading in (
            "Install and Setup",
            "Core Workflow Test",
            "Safety Workflow Test",
            "Security Scan",
            "Build Checks",
            "Launch Candidate Decision",
        ):
            self.assertIn(heading, text)
        for phrase in (
            "Real publishing remains disabled",
            "Do not call real APIs",
            "Manual Export",
            "Emergency pause",
            "scripts.launch_check",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
