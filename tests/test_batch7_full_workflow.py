from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.ai.schemas import GeneratedContentBundle, PlatformPostDraft
from scripts.db.drafts import approve_generated_draft, save_generated_bundle_to_drafts
from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.jobs.local_runner import LocalJobRunner
from scripts.services.ai_learning import AILearningService
from scripts.services.analytics import AnalyticsService
from scripts.services.engagement import EngagementService
from scripts.services.publish_queue import PublishQueueService
from scripts.services.reply_approvals import ReplyApprovalService
from scripts.services.reply_suggestions import ReplySuggestionService
from scripts.services.scheduling import CalendarSchedulingService


class Batch7FullLocalWorkflowTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        return db_path

    @staticmethod
    def _bundle() -> GeneratedContentBundle:
        return GeneratedContentBundle(
            brand_profile_id=DEMO_BRAND_ID,
            posts=[
                PlatformPostDraft(
                    platform="facebook",
                    caption=(
                        "Demo workflow draft: A seasonal exterior-care reminder "
                        "with a clear local estimate next step."
                    ),
                    headline="Seasonal exterior-care reminder",
                    hook="A quick seasonal check can prevent avoidable cleanup.",
                    hashtags=["#DemoPost", "#ExteriorCare"],
                    media_asset_ids=[],
                    call_to_action="Ask for a local estimate.",
                    safety_flags=[],
                    content_goal="get_leads",
                    content_angle="educational",
                )
            ],
            prompt_id="platform_post_generator_v1",
            prompt_version="v1",
            generation_provider="mock",
            created_at="2026-06-10T11:00:00Z",
        )

    def test_review_required_local_workflow_persists_without_external_actions(self):
        db_path = self._database()
        drafts = save_generated_bundle_to_drafts(
            db_path,
            self._bundle(),
            save_request_id="batch7-full-local-workflow",
        )
        approved = approve_generated_draft(
            db_path,
            drafts[0].id,
            actor_label="batch7-test-owner",
        )

        scheduled = CalendarSchedulingService(db_path).schedule_approved_draft(
            approved.id,
            scheduled_for="2026-06-10T12:00:00Z",
            timezone="America/New_York",
            actor_label="batch7-test-owner",
            allow_past_test_item=True,
        )
        job_summary = LocalJobRunner(db_path).run_once(
            now="2026-06-10T12:05:00Z",
        )
        exported = PublishQueueService(db_path).mark_manually_exported(
            scheduled.publishQueueItemId,
            actor_label="batch7-test-owner",
            notes="Local-only Batch 7 workflow verification.",
        )

        analytics = AnalyticsService(db_path)
        snapshot = analytics.create_manual_snapshot(
            brand_profile_id=DEMO_BRAND_ID,
            platform="facebook",
            snapshot_date="2026-06-10",
            generated_post_id=approved.id,
            scheduled_post_id=scheduled.id,
            impressions=250,
            reach=200,
            views=180,
            likes=14,
            comments=3,
            shares=2,
            saves=5,
            clicks=12,
            leads=3,
            notes="Owner-entered local workflow metrics.",
        )
        insights = analytics.create_content_insights(
            brand_profile_id=DEMO_BRAND_ID,
            source="manual",
        )

        engagement = EngagementService(db_path).ingest_mock_engagement(
            brand_profile_id=DEMO_BRAND_ID,
        )
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                UPDATE engagement_items
                SET received_at = '2026-06-10T13:00:00Z'
                WHERE source = 'mock'
                """
            )
            connection.commit()

        suggestion = ReplySuggestionService(db_path).generate(
            engagement_item_id="mock-engagement-praise-comment",
        )
        approved_reply = ReplyApprovalService(db_path).approve(
            suggestion_id=suggestion.id,
            reason="Approved locally for workflow verification.",
        )

        learning = AILearningService(db_path)
        refresh = learning.updateLearningMemory(brandProfileId=DEMO_BRAND_ID)
        report = learning.generateWeeklyReport(
            brandProfileId=DEMO_BRAND_ID,
            weekStartDate="2026-06-08",
            source="manual",
        )
        generation_context = learning.applyLearningToGenerationContext(
            brandProfileId=DEMO_BRAND_ID,
        )

        self.assertEqual(job_summary.dueChecked, 1)
        self.assertEqual(job_summary.queueReady, 1)
        self.assertEqual(exported.queueStatus, "manually_exported")
        self.assertEqual(snapshot.source, "manual")
        self.assertGreaterEqual(len(insights), 1)
        self.assertEqual(engagement.createdCount, 8)
        self.assertEqual(approved_reply.status, "approved")
        self.assertGreater(len(refresh.memories), 0)
        self.assertTrue(report.recommendations)
        self.assertTrue(generation_context["learningMetadata"]["localOnly"])
        self.assertFalse(generation_context["learningMetadata"]["externalDataSent"])
        self.assertFalse(hasattr(ReplyApprovalService(db_path), "send_reply"))

        with closing(sqlite3.connect(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            queue = connection.execute(
                "SELECT * FROM publish_queue_items WHERE id = ?",
                (scheduled.publishQueueItemId,),
            ).fetchone()
            scheduled_row = connection.execute(
                "SELECT * FROM scheduled_posts WHERE id = ?",
                (scheduled.id,),
            ).fetchone()
            attempts = connection.execute(
                """
                SELECT attempt_type
                FROM publish_attempts
                WHERE publish_queue_item_id = ?
                ORDER BY created_at, id
                """,
                (scheduled.publishQueueItemId,),
            ).fetchall()
            approval = connection.execute(
                """
                SELECT action
                FROM reply_approvals
                WHERE reply_suggestion_id = ?
                ORDER BY created_at, id
                """,
                (suggestion.id,),
            ).fetchall()
            stored_report = connection.execute(
                "SELECT * FROM weekly_reports WHERE id = ?",
                (report.id,),
            ).fetchone()

        self.assertEqual(queue["queue_status"], "manually_exported")
        self.assertEqual(scheduled_row["status"], "completed")
        self.assertIn("preflight", [row["attempt_type"] for row in attempts])
        self.assertIn("manual_export", [row["attempt_type"] for row in attempts])
        self.assertIn("approve", [row["action"] for row in approval])
        self.assertIsNotNone(stored_report)


if __name__ == "__main__":
    unittest.main()
