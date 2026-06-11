from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.db.seed_demo import seed_demo_database
from scripts.db.settings import update_app_settings
from scripts.services.diagnostics import DiagnosticsService, redact_diagnostic_text


class DiagnosticsServiceTest(unittest.TestCase):
    def _service(self) -> tuple[DiagnosticsService, tempfile.TemporaryDirectory[str]]:
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        data_dir = Path(temp_dir.name) / "data"
        data_dir.mkdir()
        update_app_settings(db_path, {"localDataDirectory": str(data_dir)})
        return DiagnosticsService(db_path), temp_dir

    def test_run_checks_returns_required_sections_and_redacted_results(self):
        service, temp_dir = self._service()
        self.addCleanup(temp_dir.cleanup)

        diagnostics = service.run_checks()
        result_ids = {result["id"] for result in diagnostics["results"]}
        section_ids = {section["id"] for section in diagnostics["sections"]}

        self.assertIn(diagnostics["overallStatus"], {"healthy", "warning", "error", "disabled", "unknown"})
        for section_id in [
            "local_storage",
            "database",
            "ai",
            "social_integrations",
            "safety",
            "queue_jobs",
            "content_workflow",
            "backups",
            "recent_errors",
        ]:
            self.assertIn(section_id, section_ids)
        for result_id in [
            "local_data_directory_exists",
            "local_data_directory_writable",
            "sqlite_database_reachable",
            "database_migrations_status",
            "mock_ai_provider_available",
            "integration_mode",
            "real_publishing_disabled",
            "emergency_pause_status",
            "job_runner_status",
            "connected_account_summary",
            "token_storage_mode",
            "secret_exposure_safety",
            "queue_blocked_count",
            "drafts_needing_review_count",
            "engagement_needing_reply_count",
            "analytics_data_availability",
            "setup_checklist_status",
            "backup_availability",
        ]:
            self.assertIn(result_id, result_ids)

        for result in diagnostics["results"]:
            self.assertEqual(
                {"id", "label", "status", "summary", "details", "recommendedAction", "checkedAt"},
                set(result),
            )
            self.assertIn(result["status"], {"healthy", "warning", "error", "disabled", "unknown"})

        serialized = json.dumps(diagnostics)
        self.assertNotIn("encrypted_access_token", serialized)
        self.assertNotIn("encrypted_refresh_token", serialized)

    def test_missing_local_directories_are_reported_as_warnings(self):
        service, temp_dir = self._service()
        self.addCleanup(temp_dir.cleanup)

        diagnostics = service.run_checks()
        by_id = {result["id"]: result for result in diagnostics["results"]}

        self.assertEqual(by_id["media_directory_exists"]["status"], "warning")
        self.assertEqual(by_id["export_directory_exists"]["status"], "warning")
        self.assertEqual(by_id["logs_directory_exists"]["status"], "warning")
        self.assertEqual(by_id["backup_directory_exists"]["status"], "warning")

    def test_export_report_writes_markdown_without_secret_values(self):
        service, temp_dir = self._service()
        self.addCleanup(temp_dir.cleanup)

        report = service.export_report(
            recent_errors=[
                "OAuth callback failed with access_token=secret-access-value and Authorization: Bearer secret-bearer-value",
            ],
        )

        report_path = Path(report["reportPath"])
        self.assertTrue(report_path.exists())
        self.assertEqual(report_path.suffix, ".md")
        self.assertIn("diagnostic-report-", report_path.name)
        text = report_path.read_text(encoding="utf-8")

        self.assertIn("Diagnostics Report", text)
        self.assertIn("Redaction notice", text)
        self.assertNotIn("secret-access-value", text)
        self.assertNotIn("secret-bearer-value", text)
        self.assertIn("[REDACTED]", text)

    def test_redacts_known_secret_patterns(self):
        raw = "client_secret=abc123 access_token=tok123 refresh_token=ref123 Authorization: Bearer live-token"

        redacted = redact_diagnostic_text(raw)

        self.assertNotIn("abc123", redacted)
        self.assertNotIn("tok123", redacted)
        self.assertNotIn("ref123", redacted)
        self.assertNotIn("live-token", redacted)
        self.assertIn("[REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()
