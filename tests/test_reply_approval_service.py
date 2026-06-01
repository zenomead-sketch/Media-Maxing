import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.services.engagement import EngagementService
from scripts.services.reply_approvals import (
    ReplyApprovalService,
    ReplyApprovalServiceError,
)
from scripts.services.reply_suggestions import ReplySuggestionService


class ReplyApprovalServiceTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        EngagementService(db_path).ingest_mock_engagement(brand_profile_id=DEMO_BRAND_ID)
        return db_path

    def _suggestion(self, db_path: Path, item_id: str = "mock-engagement-praise-comment"):
        return ReplySuggestionService(db_path).generate(engagement_item_id=item_id)

    def test_approve_is_local_only_and_updates_statuses(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path)

        approved = ReplyApprovalService(db_path).approve(suggestion_id=suggestion.id)

        self.assertEqual(approved.status, "approved")
        self.assertFalse(hasattr(ReplyApprovalService(db_path), "send_reply"))
        with closing(sqlite3.connect(db_path)) as connection:
            inbox_status = connection.execute(
                "SELECT status FROM engagement_items WHERE id = ?",
                (suggestion.engagementItemId,),
            ).fetchone()[0]
        self.assertEqual(inbox_status, "reply_approved")

    def test_edit_updates_text_tone_and_audit_history(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path)
        service = ReplyApprovalService(db_path)

        edited = service.edit_suggestion(
            suggestion_id=suggestion.id,
            suggested_reply="Thank you. We appreciate the thoughtful note.",
            tone="warm",
            reason="Owner tightened the wording.",
        )

        self.assertEqual(edited.status, "edited")
        self.assertEqual(edited.tone, "warm")
        self.assertIn("thoughtful", edited.suggestedReply)
        self.assertEqual(service.list_history(suggestion.engagementItemId)[-1].action, "edit")

    def test_critical_flag_blocks_approval_until_safe_edit(self):
        db_path = self._database()
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO engagement_items (
                  id, brand_profile_id, platform, item_type, direction,
                  content, content_redacted, received_at, sentiment, intent,
                  priority, status, requires_response, source
                ) VALUES (?, ?, 'facebook', 'comment', 'inbound', ?, ?,
                  '2026-06-01T12:00:00Z', 'neutral', 'question', 'normal',
                  'needs_reply', 1, 'manual')
                """,
                (
                    "manual-guarantee-approval",
                    DEMO_BRAND_ID,
                    "Can you guarantee the result?",
                    "Can you guarantee the result?",
                ),
            )
            connection.commit()
        suggestion = ReplySuggestionService(db_path).generate(
            engagement_item_id="manual-guarantee-approval"
        )
        service = ReplyApprovalService(db_path)

        with self.assertRaisesRegex(
            ReplyApprovalServiceError,
            "critical safety flags",
        ):
            service.approve(suggestion_id=suggestion.id)

        edited = service.edit_suggestion(
            suggestion_id=suggestion.id,
            suggested_reply=(
                "Thanks for asking. Please send the project details so a person can "
                "review the scope and explain the next step."
            ),
            reason="Removed unsupported guarantee language.",
        )
        approved = service.approve(suggestion_id=edited.id)

        self.assertEqual(edited.blockingFlags, [])
        self.assertEqual(approved.status, "approved")

    def test_reject_marks_suggestion_rejected_and_item_needs_reply(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path)

        rejected = ReplyApprovalService(db_path).reject(
            suggestion_id=suggestion.id,
            reason="Needs a more specific next step.",
        )

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(self._item_status(db_path, suggestion.engagementItemId), "needs_reply")

    def test_mark_replied_manually_records_local_status(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path)

        ReplyApprovalService(db_path).mark_replied_manually(
            engagement_item_id=suggestion.engagementItemId,
            suggestion_id=suggestion.id,
        )

        self.assertEqual(
            self._item_status(db_path, suggestion.engagementItemId),
            "replied_manually",
        )

    def test_escalate_spam_and_archive_are_soft_status_actions(self):
        db_path = self._database()
        service = ReplyApprovalService(db_path)

        service.escalate(engagement_item_id="mock-engagement-complaint")
        service.mark_spam(engagement_item_id="mock-engagement-spam")
        service.archive(engagement_item_id="mock-engagement-general-comment")

        self.assertEqual(self._item_status(db_path, "mock-engagement-complaint"), "escalated")
        self.assertEqual(self._item_status(db_path, "mock-engagement-spam"), "spam")
        self.assertEqual(self._item_status(db_path, "mock-engagement-general-comment"), "archived")

    def test_spam_suggestion_cannot_be_approved(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path, "mock-engagement-spam")

        with self.assertRaisesRegex(ReplyApprovalServiceError, "marked spam"):
            ReplyApprovalService(db_path).approve(suggestion_id=suggestion.id)

    def test_all_actions_write_audit_rows(self):
        db_path = self._database()
        suggestion = self._suggestion(db_path)
        service = ReplyApprovalService(db_path)
        service.edit_suggestion(
            suggestion_id=suggestion.id,
            suggested_reply="Thank you for the kind note.",
        )
        service.approve(suggestion_id=suggestion.id)
        service.mark_replied_manually(
            engagement_item_id=suggestion.engagementItemId,
            suggestion_id=suggestion.id,
        )

        actions = [entry.action for entry in service.list_history(suggestion.engagementItemId)]
        self.assertEqual(actions, ["suggest", "edit", "approve", "mark_replied_manually"])

    @staticmethod
    def _item_status(db_path: Path, item_id: str) -> str:
        with closing(sqlite3.connect(db_path)) as connection:
            return connection.execute(
                "SELECT status FROM engagement_items WHERE id = ?",
                (item_id,),
            ).fetchone()[0]


if __name__ == "__main__":
    unittest.main()
