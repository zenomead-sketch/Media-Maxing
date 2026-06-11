from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.services.ai_learning import AILearningService
from scripts.services.ai_memory import _confidence
from scripts.services.engagement import EngagementService


class AILearningServiceTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        return db_path

    def test_facade_refreshes_memory_and_returns_bounded_generation_context(self):
        service = AILearningService(self._database())

        result = service.updateLearningMemory(brandProfileId=DEMO_BRAND_ID)
        context = service.applyLearningToGenerationContext(
            brandProfileId=DEMO_BRAND_ID,
            limit=3,
        )

        self.assertGreaterEqual(result.createdCount, 1)
        self.assertLessEqual(len(context["activeAIMemory"]), 3)
        self.assertEqual(context["learningMetadata"]["memoryLimit"], 3)
        self.assertTrue(context["learningMetadata"]["localOnly"])
        self.assertFalse(context["learningMetadata"]["externalDataSent"])

    def test_refresh_uses_brand_media_performance_and_direct_engagement_evidence(self):
        db_path = self._database()
        EngagementService(db_path).ingest_mock_engagement(brand_profile_id=DEMO_BRAND_ID)

        memories = AILearningService(db_path).updateLearningMemory(
            brandProfileId=DEMO_BRAND_ID
        ).memories

        self.assertTrue(any(memory.memoryType == "brand_rule" for memory in memories))
        self.assertTrue(
            any("postPerformanceMetricIds" in memory.evidence for memory in memories)
        )
        media = next(
            memory for memory in memories if "relatedMediaAssetIds" in memory.evidence
            and memory.title.startswith("Reviewed media metadata")
        )
        complaint = next(
            memory
            for memory in memories
            if memory.title == "Complaint replies need empathetic owner escalation"
        )
        self.assertGreaterEqual(len(media.evidence["relatedMediaAssetIds"]), 1)
        self.assertFalse(complaint.evidence["privateEngagementContentStored"])
        self.assertIn("mock-engagement-complaint", complaint.evidence["engagementItemIds"])

    def test_current_rejected_draft_state_creates_caution_memory_without_log_dependency(self):
        db_path = self._database()
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                UPDATE generated_posts
                SET approval_status = 'rejected'
                WHERE id = 'demo-post-gutter-reminder'
                """
            )
            connection.commit()

        memories = AILearningService(db_path).updateLearningMemory(
            brandProfileId=DEMO_BRAND_ID
        ).memories
        rejected = next(
            memory for memory in memories if memory.memoryType == "rejected_strategy"
        )

        self.assertIn("demo-post-gutter-reminder", rejected.evidence["generatedPostIds"])
        self.assertIn("owner", rejected.content.lower())

    def test_confidence_requires_volume_and_consistency(self):
        self.assertEqual(_confidence(4, consistent=True), "low")
        self.assertEqual(_confidence(5, consistent=True), "medium")
        self.assertEqual(_confidence(20, consistent=True), "medium")
        self.assertEqual(_confidence(21, consistent=False), "medium")
        self.assertEqual(_confidence(21, consistent=True), "high")

    def test_weekly_report_contains_requested_local_evidence_sections(self):
        db_path = self._database()
        EngagementService(db_path).ingest_mock_engagement(brand_profile_id=DEMO_BRAND_ID)
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                "UPDATE engagement_items SET received_at = '2026-06-10T12:00:00Z'"
            )
            connection.commit()

        report = AILearningService(db_path).generateWeeklyReport(
            brandProfileId=DEMO_BRAND_ID,
            weekStartDate="2026-06-08",
        )

        self.assertGreaterEqual(len(report.recommendations), 1)
        self.assertGreaterEqual(len(report.nextWeekContentSuggestions), 1)
        self.assertGreaterEqual(len(report.learningUpdates), 1)
        self.assertGreaterEqual(len(report.leadSignals), 1)
        self.assertEqual(report.engagementSummary["totalItems"], 8)
        self.assertEqual(report.engagementSummary["complaints"], 1)
        self.assertEqual(report.engagementSummary["leadSignals"], 3)
        self.assertIn("analyticsSnapshotIds", report.evidence)
        self.assertFalse(report.evidence["privateEngagementContentStored"])
        self.assertEqual(report.promptMetadata["generator"], "rule_based_local_v1")
        self.assertFalse(report.promptMetadata["aiProviderCalled"])
        self.assertFalse(report.promptMetadata["externalDataSent"])

    def test_cli_runs_without_external_calls(self):
        db_path = self._database()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.services.ai_learning",
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
        self.assertIn("external_ai_calls=false", result.stdout)
        self.assertIn("external_platform_calls=false", result.stdout)
        self.assertIn("local_only=true", result.stdout)


if __name__ == "__main__":
    unittest.main()
