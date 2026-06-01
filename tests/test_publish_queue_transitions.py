from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.init_db import initialize_database
from scripts.services.publish_queue import PublishQueueError, PublishQueueService


def _json(value):
    return json.dumps(value, sort_keys=True)


class PublishQueueTransitionsTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        initialize_database(db_path)
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO brand_profiles (
                  id, business_name, services_json, locations_json,
                  supported_claims_json, blocked_phrases_json, preferences_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("brand-queue", "Queue Test Exterior Care", "[]", "[]", "[]", "[]", "{}"),
            )
            connection.commit()
        return db_path

    def _queue_item(
        self,
        db_path: Path,
        *,
        suffix: str,
        queue_status: str = "waiting",
        preflight_status: str = "not_checked",
        mock_publish_enabled: bool = False,
    ) -> tuple[str, str, str]:
        draft_id = f"draft-{suffix}"
        scheduled_id = f"scheduled-{suffix}"
        queue_id = f"queue-{suffix}"
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO generated_posts (
                  id, brand_profile_id, platform, caption, approval_status,
                  safety_flags_json, generation_provider
                ) VALUES (?, 'brand-queue', 'facebook', ?, 'approved', '[]', 'mock')
                """,
                (draft_id, f"Local queue fixture {suffix}."),
            )
            connection.execute(
                """
                INSERT INTO scheduled_posts (
                  id, generated_post_id, brand_profile_id, platform,
                  scheduled_for, timezone, status, caption_snapshot,
                  media_asset_ids_json
                ) VALUES (?, ?, 'brand-queue', 'facebook', ?, ?, 'scheduled', ?, '[]')
                """,
                (
                    scheduled_id,
                    draft_id,
                    "2026-06-10T13:00:00Z",
                    "America/New_York",
                    f"Local queue fixture {suffix}.",
                ),
            )
            connection.execute(
                """
                INSERT INTO publish_queue_items (
                  id, scheduled_post_id, generated_post_id, brand_profile_id,
                  platform, queue_status, due_at, timezone, preflight_status,
                  mock_publish_enabled
                ) VALUES (?, ?, ?, 'brand-queue', 'facebook', ?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    scheduled_id,
                    draft_id,
                    queue_status,
                    "2026-06-10T13:00:00Z",
                    "America/New_York",
                    preflight_status,
                    int(mock_publish_enabled),
                ),
            )
            connection.execute(
                """
                UPDATE scheduled_posts
                SET publish_queue_item_id = ?
                WHERE id = ?
                """,
                (queue_id, scheduled_id),
            )
            connection.commit()
        return draft_id, scheduled_id, queue_id

    def _statuses(self, db_path: Path, draft_id: str, scheduled_id: str, queue_id: str):
        with closing(sqlite3.connect(db_path)) as connection:
            return connection.execute(
                """
                SELECT
                  generated_posts.publish_readiness_status,
                  scheduled_posts.status,
                  publish_queue_items.queue_status
                FROM generated_posts
                JOIN scheduled_posts ON scheduled_posts.id = ?
                JOIN publish_queue_items ON publish_queue_items.id = ?
                WHERE generated_posts.id = ?
                """,
                (scheduled_id, queue_id, draft_id),
            ).fetchone()

    def test_cancel_updates_queue_schedule_draft_and_audit(self):
        db_path = self._database()
        draft_id, scheduled_id, queue_id = self._queue_item(db_path, suffix="cancel")

        result = PublishQueueService(db_path).cancel(queue_id, reason="Owner canceled locally.")

        self.assertEqual(result.queueStatus, "canceled")
        self.assertEqual(
            self._statuses(db_path, draft_id, scheduled_id, queue_id),
            ("canceled", "canceled", "canceled"),
        )
        with closing(sqlite3.connect(db_path)) as connection:
            audit = connection.execute(
                "SELECT action FROM approval_logs WHERE entity_id = ?",
                (scheduled_id,),
            ).fetchone()
        self.assertEqual(audit, ("queue_item_canceled",))

    def test_skip_updates_queue_and_marks_schedule_needs_attention(self):
        db_path = self._database()
        draft_id, scheduled_id, queue_id = self._queue_item(db_path, suffix="skip")

        result = PublishQueueService(db_path).skip(queue_id)

        self.assertEqual(result.queueStatus, "skipped")
        self.assertEqual(
            self._statuses(db_path, draft_id, scheduled_id, queue_id),
            ("skipped", "needs_attention", "skipped"),
        )

    def test_manual_and_mock_completion_update_draft_readiness(self):
        db_path = self._database()
        manual = self._queue_item(
            db_path,
            suffix="manual",
            queue_status="ready",
            preflight_status="warnings",
        )
        mock = self._queue_item(
            db_path,
            suffix="mock",
            queue_status="ready",
            preflight_status="passed",
            mock_publish_enabled=True,
        )

        PublishQueueService(db_path).mark_manually_exported(manual[2])
        PublishQueueService(db_path).mock_publish(mock[2])

        self.assertEqual(self._statuses(db_path, *manual), ("manually_exported", "completed", "manually_exported"))
        self.assertEqual(self._statuses(db_path, *mock), ("mock_published", "completed", "mock_published"))

    def test_processed_queue_item_cannot_be_skipped(self):
        db_path = self._database()
        _, _, queue_id = self._queue_item(
            db_path,
            suffix="processed",
            queue_status="manually_exported",
        )

        with self.assertRaises(PublishQueueError) as error:
            PublishQueueService(db_path).skip(queue_id)

        self.assertIn("queue_already_processed", error.exception.error_codes)


if __name__ == "__main__":
    unittest.main()
