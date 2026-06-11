from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.services.weekly_reports import WeeklyReportService


class WeeklyReportServiceTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        return db_path

    def test_mock_only_report_is_labeled_ai_mock_and_idempotent(self):
        db_path = self._database()
        service = WeeklyReportService(db_path)

        first = service.generate_report(
            brand_profile_id=DEMO_BRAND_ID,
            week_start_date="2026-06-08",
        )
        second = service.generate_report(
            brand_profile_id=DEMO_BRAND_ID,
            week_start_date="2026-06-08",
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.generatedBy, "ai_mock")
        self.assertTrue(second.metricTotals["demo"])
        self.assertEqual(second.metricTotals["sources"], ["mock"])
        self.assertIn("fake mock", second.summary.lower())
        matching = [
            report
            for report in service.list_reports(brand_profile_id=DEMO_BRAND_ID)
            if report.id == second.id
        ]
        self.assertEqual(len(matching), 1)

    def test_empty_week_generates_honest_local_report(self):
        db_path = self._database()
        report = WeeklyReportService(db_path).generate_report(
            brand_profile_id=DEMO_BRAND_ID,
            week_start_date="2027-01-04",
        )

        self.assertEqual(report.generatedBy, "system")
        self.assertEqual(report.metricTotals["totalPosts"], 0)
        self.assertEqual(report.metricTotals["sources"], [])
        self.assertIn("No local analytics snapshots", report.summary)

    def test_report_contains_local_summary_sections(self):
        db_path = self._database()
        report = WeeklyReportService(db_path).generate_report(
            brand_profile_id=DEMO_BRAND_ID,
            week_start_date="2026-06-08",
        )

        self.assertEqual(report.weekEndDate, "2026-06-14")
        self.assertGreaterEqual(len(report.wins), 1)
        self.assertGreaterEqual(len(report.concerns), 1)
        self.assertGreaterEqual(len(report.recommendations), 1)
        self.assertIn("instagram", report.platformBreakdown)
        self.assertGreaterEqual(len(report.topPosts), 1)
        self.assertGreaterEqual(len(report.underperformingPosts), 1)
        self.assertGreaterEqual(len(report.leadSignals), 1)
        self.assertGreaterEqual(len(report.learningUpdates), 1)
        self.assertGreaterEqual(len(report.nextWeekContentSuggestions), 1)
        self.assertIn("analyticsSnapshotIds", report.evidence)
        self.assertFalse(report.evidence["privateEngagementContentStored"])
        self.assertEqual(report.promptMetadata["generator"], "rule_based_local_v1")
        self.assertFalse(report.promptMetadata["aiProviderCalled"])

    def test_cli_generation_is_local_only(self):
        db_path = self._database()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.services.weekly_reports",
                "--database",
                str(db_path),
                "--brand-profile-id",
                DEMO_BRAND_ID,
                "--week-start-date",
                "2026-06-08",
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"generatedBy": "ai_mock"', result.stdout)
        self.assertIn("external_platform_calls=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
