from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings


READY_PREFLIGHT_STATUSES = {"passed", "warnings"}
FINAL_QUEUE_STATUSES = {
    "mock_published",
    "manually_exported",
    "platform_published",
    "canceled",
    "skipped",
}


class PublishQueueError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class QueueActionResult:
    id: str
    scheduledPostId: str
    queueStatus: str
    preflightStatus: str
    attemptId: str | None = None
    warnings: list[str] = field(default_factory=list)


class PublishQueueService:
    """Local-only queue actions for manual export and mock publishing.

    This service updates SQLite records and writes local publish attempts. It
    never calls external APIs or creates real social posts.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def mark_manually_exported(
        self,
        queue_item_id: str,
        *,
        actor_label: str = "local_user",
        notes: str | None = None,
    ) -> QueueActionResult:
        queue_row = self._require_queue_row(queue_item_id)
        scheduled_row = self._require_scheduled_row(queue_row["scheduled_post_id"])
        self._ensure_not_emergency_paused("manual export completion")
        if queue_row["queue_status"] in {"canceled", "skipped"}:
            raise PublishQueueError(
                "Canceled or skipped queue items cannot be marked manually exported.",
                ["queue_not_exportable"],
            )
        if queue_row["queue_status"] in {"mock_published", "manually_exported", "platform_published"}:
            raise PublishQueueError(
                "Queue item has already been completed.",
                ["queue_already_completed"],
            )
        if queue_row["preflight_status"] not in READY_PREFLIGHT_STATUSES:
            raise PublishQueueError(
                "Manual export completion requires passed or warning-only preflight.",
                ["preflight_not_ready"],
            )

        now = _now_utc()
        attempt_id = str(uuid.uuid4())
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            connection.execute(
                """
                UPDATE publish_queue_items
                SET queue_status = 'manually_exported',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, queue_row["id"]),
            )
            connection.execute(
                """
                UPDATE scheduled_posts
                SET status = 'completed',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, scheduled_row["id"]),
            )
            self._update_generated_post_readiness(
                connection,
                queue_row["generated_post_id"],
                "manually_exported",
                now,
            )
            connection.execute(
                """
                INSERT INTO publish_attempts (
                  id, publish_queue_item_id, scheduled_post_id, platform,
                  attempt_type, attempt_status, started_at, finished_at,
                  provider_response_json, created_at
                ) VALUES (?, ?, ?, ?, 'manual_export', 'succeeded', ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    queue_row["id"],
                    scheduled_row["id"],
                    queue_row["platform"],
                    now,
                    now,
                    _json(
                        {
                            "source": "publish_queue_service",
                            "actorLabel": actor_label,
                            "notes": notes,
                            "realPublishing": False,
                            "manualExportOnly": True,
                        }
                    ),
                    now,
                ),
            )
            connection.commit()

        return self._result(queue_row["id"], attempt_id=attempt_id)

    def mock_publish(
        self,
        queue_item_id: str,
        *,
        actor_label: str = "local_user",
    ) -> QueueActionResult:
        queue_row = self._require_queue_row(queue_item_id)
        scheduled_row = self._require_scheduled_row(queue_row["scheduled_post_id"])
        self._ensure_not_emergency_paused("mock publish")
        if queue_row["queue_status"] != "ready":
            raise PublishQueueError(
                "Only ready queue items can be mock-published.",
                ["queue_not_ready"],
            )
        if queue_row["preflight_status"] != "passed":
            raise PublishQueueError(
                "Mock publish requires fully passed preflight.",
                ["preflight_not_passed"],
            )
        if not bool(queue_row["mock_publish_enabled"]):
            raise PublishQueueError(
                "Mock publishing is disabled for this queue item.",
                ["mock_publish_disabled"],
            )

        now = _now_utc()
        attempt_id = str(uuid.uuid4())
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            connection.execute(
                """
                UPDATE publish_queue_items
                SET queue_status = 'mock_published',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, queue_row["id"]),
            )
            connection.execute(
                """
                UPDATE scheduled_posts
                SET status = 'completed',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, scheduled_row["id"]),
            )
            self._update_generated_post_readiness(
                connection,
                queue_row["generated_post_id"],
                "mock_published",
                now,
            )
            connection.execute(
                """
                INSERT INTO publish_attempts (
                  id, publish_queue_item_id, scheduled_post_id, platform,
                  attempt_type, attempt_status, started_at, finished_at,
                  provider_response_json, created_at
                ) VALUES (?, ?, ?, ?, 'mock_publish', 'succeeded', ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    queue_row["id"],
                    scheduled_row["id"],
                    queue_row["platform"],
                    now,
                    now,
                    _json(
                        {
                            "source": "publish_queue_service",
                            "actorLabel": actor_label,
                            "realPublishing": False,
                            "mockOnly": True,
                        }
                    ),
                    now,
                ),
            )
            connection.commit()

        return self._result(queue_row["id"], attempt_id=attempt_id)

    def cancel(
        self,
        queue_item_id: str,
        *,
        actor_label: str = "local_user",
        reason: str | None = None,
    ) -> QueueActionResult:
        queue_row = self._require_queue_row(queue_item_id)
        if queue_row["queue_status"] in FINAL_QUEUE_STATUSES:
            if queue_row["queue_status"] == "canceled":
                return self._result(queue_row["id"])
            raise PublishQueueError(
                "Completed or skipped queue items cannot be canceled.",
                ["queue_already_processed"],
            )
        if queue_row["queue_status"] == "processing":
            raise PublishQueueError(
                "Processing queue items cannot be canceled.",
                ["queue_processing"],
            )

        now = _now_utc()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            connection.execute(
                """
                UPDATE publish_queue_items
                SET queue_status = 'canceled',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, queue_row["id"]),
            )
            connection.execute(
                """
                UPDATE scheduled_posts
                SET status = 'canceled',
                    canceled_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, now, queue_row["scheduled_post_id"]),
            )
            self._update_generated_post_readiness(
                connection,
                queue_row["generated_post_id"],
                "canceled",
                now,
            )
            self._append_audit_log(
                connection,
                scheduled_post_id=queue_row["scheduled_post_id"],
                action="queue_item_canceled",
                actor_label=actor_label,
                notes=reason or "Publish queue item canceled locally.",
                changed_fields={
                    "publishQueueItemId": queue_row["id"],
                    "previousQueueStatus": queue_row["queue_status"],
                    "queueStatus": "canceled",
                },
                created_at=now,
            )
            connection.commit()
        return self._result(queue_row["id"])

    def skip(
        self,
        queue_item_id: str,
        *,
        actor_label: str = "local_user",
        reason: str | None = None,
    ) -> QueueActionResult:
        queue_row = self._require_queue_row(queue_item_id)
        if queue_row["queue_status"] in FINAL_QUEUE_STATUSES:
            if queue_row["queue_status"] == "skipped":
                return self._result(queue_row["id"])
            raise PublishQueueError(
                "Completed or canceled queue items cannot be skipped.",
                ["queue_already_processed"],
            )
        if queue_row["queue_status"] == "processing":
            raise PublishQueueError(
                "Processing queue items cannot be skipped.",
                ["queue_processing"],
            )

        now = _now_utc()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            connection.execute(
                """
                UPDATE publish_queue_items
                SET queue_status = 'skipped',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, queue_row["id"]),
            )
            connection.execute(
                """
                UPDATE scheduled_posts
                SET status = 'needs_attention',
                    updated_at = ?
                WHERE id = ?
                """,
                (now, queue_row["scheduled_post_id"]),
            )
            self._update_generated_post_readiness(
                connection,
                queue_row["generated_post_id"],
                "skipped",
                now,
            )
            self._append_audit_log(
                connection,
                scheduled_post_id=queue_row["scheduled_post_id"],
                action="queue_item_skipped",
                actor_label=actor_label,
                notes=reason or "Publish queue item skipped locally.",
                changed_fields={
                    "publishQueueItemId": queue_row["id"],
                    "previousQueueStatus": queue_row["queue_status"],
                    "queueStatus": "skipped",
                    "scheduledPostStatus": "needs_attention",
                },
                created_at=now,
            )
            connection.commit()
        return self._result(queue_row["id"])

    def _ensure_not_emergency_paused(self, action: str) -> None:
        if load_app_settings(self.database_path).emergencyPauseEnabled:
            raise PublishQueueError(
                f"Emergency pause blocks {action}.",
                ["emergency_pause_enabled"],
            )

    def _update_generated_post_readiness(
        self,
        connection: sqlite3.Connection,
        generated_post_id: str,
        readiness_status: str,
        updated_at: str,
    ) -> None:
        connection.execute(
            """
            UPDATE generated_posts
            SET publish_readiness_status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (readiness_status, updated_at, generated_post_id),
        )

    def _append_audit_log(
        self,
        connection: sqlite3.Connection,
        *,
        scheduled_post_id: str,
        action: str,
        actor_label: str,
        notes: str,
        changed_fields: dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO approval_logs (
              id, entity_type, entity_id, action, actor_label,
              notes, changed_fields_json, created_at
            ) VALUES (?, 'scheduled_post', ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                scheduled_post_id,
                action,
                actor_label,
                notes,
                _json(changed_fields),
                created_at,
            ),
        )

    def _result(self, queue_item_id: str, *, attempt_id: str | None = None) -> QueueActionResult:
        row = self._require_queue_row(queue_item_id)
        return QueueActionResult(
            id=row["id"],
            scheduledPostId=row["scheduled_post_id"],
            queueStatus=row["queue_status"],
            preflightStatus=row["preflight_status"],
            attemptId=attempt_id,
            warnings=_decode_json(row["preflight_warnings_json"], []),
        )

    def _require_queue_row(self, queue_item_id: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM publish_queue_items WHERE id = ?",
                (queue_item_id,),
            ).fetchone()
        if row is None:
            raise PublishQueueError(
                f"Publish queue item {queue_item_id!r} does not exist.",
                ["queue_item_not_found"],
            )
        return row

    def _require_scheduled_row(self, scheduled_post_id: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM scheduled_posts WHERE id = ?",
                (scheduled_post_id,),
            ).fetchone()
        if row is None:
            raise PublishQueueError(
                f"Scheduled post {scheduled_post_id!r} does not exist.",
                ["scheduled_post_not_found"],
            )
        return row


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback
