from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.init_db import initialize_database
from scripts.db.settings import load_app_settings
from scripts.db.seed_demo import seed_demo_database
from scripts.services.safety_center import SafetyCenterService


class SafetyCenterServiceTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        return db_path

    def test_state_summarizes_pause_status_and_safety_counts(self):
        db_path = self._database()

        state = SafetyCenterService(db_path).get_state()

        self.assertFalse(state["emergencyPause"]["enabled"])
        self.assertIn("scheduling_new_posts", state["blockedActions"])
        self.assertIn("editing_drafts", state["allowedActions"])
        self.assertEqual(state["publishingSafety"]["realPublishingEnabled"], False)
        self.assertIn("approval_queue", [level["id"] for level in state["automationLevels"]])
        self.assertGreaterEqual(state["pendingApprovals"]["draftsNeedingReview"], 0)
        self.assertIn("criticalSafetyFlags", state)

    def test_enable_disable_pause_records_audit_and_forces_safe_automation_level(self):
        db_path = self._database()
        service = SafetyCenterService(db_path)

        enabled = service.set_emergency_pause(
            True,
            actor_type="test",
            reason="Safety drill.",
        )
        disabled = service.set_emergency_pause(
            False,
            actor_type="test",
            reason="Safety drill complete.",
        )

        settings = load_app_settings(db_path)
        actions = [entry["action"] for entry in service.list_audit_logs()]

        self.assertTrue(enabled["emergencyPause"]["enabled"])
        self.assertFalse(disabled["emergencyPause"]["enabled"])
        self.assertFalse(settings.emergencyPauseEnabled)
        self.assertEqual(settings.automationLevel, "approval_queue")
        self.assertIn("emergency_pause_enabled", actions)
        self.assertIn("emergency_pause_disabled", actions)

    def test_kill_switch_pause_all_and_cancel_future_scheduled_posts_are_reversible_state_changes(self):
        db_path = self._database()
        service = SafetyCenterService(db_path)

        pause_result = service.run_kill_switch_action(
            "pause_all_automation",
            actor_type="test",
            confirmation_phrase="PAUSE ALL",
        )
        cancel_result = service.run_kill_switch_action(
            "cancel_future_scheduled_posts",
            actor_type="test",
            confirmation_phrase="CANCEL FUTURE POSTS",
        )

        with closing(sqlite3.connect(db_path)) as connection:
            future_active = connection.execute(
                """
                SELECT COUNT(*)
                FROM scheduled_posts
                WHERE status IN ('scheduled', 'queued', 'needs_attention')
                """
            ).fetchone()[0]
            queue_active = connection.execute(
                """
                SELECT COUNT(*)
                FROM publish_queue_items
                WHERE queue_status IN ('waiting', 'ready', 'blocked', 'failed')
                """
            ).fetchone()[0]

        actions = [entry["action"] for entry in service.list_audit_logs()]
        self.assertTrue(pause_result["emergencyPause"]["enabled"])
        self.assertEqual(cancel_result["action"], "cancel_future_scheduled_posts")
        self.assertEqual(future_active, 0)
        self.assertEqual(queue_active, 0)
        self.assertIn("kill_switch_action_started", actions)
        self.assertIn("scheduled_posts_canceled", actions)
        self.assertIn("kill_switch_action_completed", actions)

    def test_kill_switch_requires_confirmation_phrase(self):
        db_path = self._database()

        with self.assertRaises(ValueError):
            SafetyCenterService(db_path).run_kill_switch_action(
                "cancel_future_scheduled_posts",
                actor_type="test",
                confirmation_phrase="wrong",
            )


if __name__ == "__main__":
    unittest.main()
