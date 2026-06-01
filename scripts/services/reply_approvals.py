from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.ai.schemas import ReplySuggestionOutput, SchemaValidationError
from scripts.db.engagement_models import REPLY_APPROVAL_ACTOR_TYPES
from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.services.reply_suggestions import (
    ReplySuggestion,
    run_reply_safety_review,
)


class ReplyApprovalServiceError(RuntimeError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class ReplyApprovalRecord:
    id: str
    replySuggestionId: str | None
    engagementItemId: str
    action: str
    previousStatus: str | None
    newStatus: str
    reason: str | None
    actorType: str
    createdAt: str


class ReplyApprovalService:
    """Manage local reply review decisions without sending external replies."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def edit_suggestion(
        self,
        *,
        suggestion_id: str,
        suggested_reply: str,
        tone: str | None = None,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> ReplySuggestion:
        self._require_actor_type(actor_type)
        with self._connection() as connection:
            suggestion = self._require_suggestion(connection, suggestion_id)
            item = self._require_engagement_item(connection, suggestion["engagement_item_id"])
            output = self._review_edit(
                suggestion=suggestion,
                item=item,
                suggested_reply=suggested_reply,
                tone=tone,
            )
            now = _now_utc()
            with connection:
                connection.execute(
                    """
                    UPDATE reply_suggestions
                    SET suggested_reply = ?,
                      tone = ?,
                      safety_flags_json = ?,
                      blocking_flags_json = ?,
                      safety_review_json = ?,
                      needs_human_review = 1,
                      status = 'edited',
                      updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        output.suggested_reply,
                        output.tone,
                        _json([flag.code for flag in output.safety_flags]),
                        _json(output.blocking_flags),
                        _json([flag.to_dict() for flag in output.safety_flags]),
                        now,
                        suggestion_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE engagement_items
                    SET status = 'reply_suggested',
                      updated_at = ?
                    WHERE id = ?
                    """,
                    (now, item["id"]),
                )
                self._append_audit(
                    connection,
                    suggestion_id=suggestion_id,
                    engagement_item_id=item["id"],
                    action="edit",
                    previous_status=item["status"],
                    new_status="reply_suggested",
                    reason=reason or "Owner edited the local reply draft.",
                    actor_type=actor_type,
                    created_at=now,
                )
            return self._get_suggestion(connection, suggestion_id)

    def approve(
        self,
        *,
        suggestion_id: str,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> ReplySuggestion:
        self._require_actor_type(actor_type)
        with self._connection() as connection:
            suggestion = self._require_suggestion(connection, suggestion_id)
            item = self._require_engagement_item(connection, suggestion["engagement_item_id"])
            if item["status"] == "spam" or item["intent"] == "spam":
                raise ReplyApprovalServiceError(
                    "This item is marked spam. Reply approval is not recommended.",
                    ["spam_reply_approval_blocked"],
                )
            stored_blocking = _decode_json(suggestion["blocking_flags_json"], [])
            if stored_blocking:
                raise ReplyApprovalServiceError(
                    "This suggestion has critical safety flags. Edit it before approving.",
                    ["critical_safety_flags"],
                )
            review = run_reply_safety_review(
                engagement_content=item["content"],
                intent=item["intent"],
                suggested_reply=suggestion["suggested_reply"],
                include_inbound_request_risks=False,
            )
            if review.blocking_flags:
                raise ReplyApprovalServiceError(
                    "This suggestion has critical safety flags. Edit it before approving.",
                    ["critical_safety_flags"],
                )
            now = _now_utc()
            with connection:
                connection.execute(
                    """
                    UPDATE reply_suggestions
                    SET safety_flags_json = ?,
                      blocking_flags_json = ?,
                      safety_review_json = ?,
                      needs_human_review = 1,
                      status = 'approved',
                      updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        _json([flag.code for flag in review.flags]),
                        _json(review.blocking_flags),
                        _json([flag.to_dict() for flag in review.flags]),
                        now,
                        suggestion_id,
                    ),
                )
                connection.execute(
                    """
                    UPDATE engagement_items
                    SET status = 'reply_approved',
                      updated_at = ?
                    WHERE id = ?
                    """,
                    (now, item["id"]),
                )
                self._append_audit(
                    connection,
                    suggestion_id=suggestion_id,
                    engagement_item_id=item["id"],
                    action="approve",
                    previous_status=item["status"],
                    new_status="reply_approved",
                    reason=reason or "Approved locally only. No external reply was sent.",
                    actor_type=actor_type,
                    created_at=now,
                )
            return self._get_suggestion(connection, suggestion_id)

    def reject(
        self,
        *,
        suggestion_id: str,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> ReplySuggestion:
        return self._update_suggestion_and_item(
            suggestion_id=suggestion_id,
            suggestion_status="rejected",
            engagement_status="needs_reply",
            action="reject",
            reason=reason or "Owner rejected the local reply draft.",
            actor_type=actor_type,
        )

    def mark_replied_manually(
        self,
        *,
        engagement_item_id: str,
        suggestion_id: str | None = None,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> None:
        self._update_item_status(
            engagement_item_id=engagement_item_id,
            engagement_status="replied_manually",
            action="mark_replied_manually",
            suggestion_id=suggestion_id,
            reason=reason or "Owner recorded a reply handled outside the app.",
            actor_type=actor_type,
        )

    def escalate(
        self,
        *,
        engagement_item_id: str,
        suggestion_id: str | None = None,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> None:
        self._update_item_status(
            engagement_item_id=engagement_item_id,
            engagement_status="escalated",
            action="escalate",
            suggestion_id=suggestion_id,
            reason=reason or "Escalated for owner review.",
            actor_type=actor_type,
        )

    def mark_spam(
        self,
        *,
        engagement_item_id: str,
        suggestion_id: str | None = None,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> None:
        self._update_item_status(
            engagement_item_id=engagement_item_id,
            engagement_status="spam",
            action="mark_spam",
            suggestion_id=suggestion_id,
            reason=reason or "Marked as spam locally. No reply was sent.",
            actor_type=actor_type,
        )

    def archive(
        self,
        *,
        engagement_item_id: str,
        suggestion_id: str | None = None,
        reason: str | None = None,
        actor_type: str = "user",
    ) -> None:
        self._update_item_status(
            engagement_item_id=engagement_item_id,
            engagement_status="archived",
            action="archive",
            suggestion_id=suggestion_id,
            suggestion_status="archived" if suggestion_id else None,
            reason=reason or "Archived locally. No record was deleted.",
            actor_type=actor_type,
        )

    def list_history(self, engagement_item_id: str) -> list[ReplyApprovalRecord]:
        with self._connection() as connection:
            self._require_engagement_item(connection, engagement_item_id)
            rows = connection.execute(
                """
                SELECT *
                FROM reply_approvals
                WHERE engagement_item_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (engagement_item_id,),
            ).fetchall()
        return [_row_to_approval(row) for row in rows]

    def _review_edit(
        self,
        *,
        suggestion: sqlite3.Row,
        item: sqlite3.Row,
        suggested_reply: str,
        tone: str | None,
    ) -> ReplySuggestionOutput:
        review = run_reply_safety_review(
            engagement_content=item["content"],
            intent=item["intent"],
            suggested_reply=suggested_reply,
            include_inbound_request_risks=False,
        )
        try:
            return ReplySuggestionOutput(
                suggested_reply=suggested_reply,
                tone=tone or suggestion["tone"] or "helpful",
                confidence=suggestion["confidence"],
                safety_flags=review.flags,
                blocking_flags=review.blocking_flags,
                recommended_action=suggestion["recommended_action"],
                needs_human_review=True,
                reason_summary=suggestion["reasoning_summary"] or "Owner-edited local draft.",
            )
        except SchemaValidationError as error:
            raise ReplyApprovalServiceError(
                f"Edited reply was rejected: {error}",
                ["reply_edit_invalid"],
            ) from error

    def _update_suggestion_and_item(
        self,
        *,
        suggestion_id: str,
        suggestion_status: str,
        engagement_status: str,
        action: str,
        reason: str,
        actor_type: str,
    ) -> ReplySuggestion:
        self._require_actor_type(actor_type)
        with self._connection() as connection:
            suggestion = self._require_suggestion(connection, suggestion_id)
            item = self._require_engagement_item(connection, suggestion["engagement_item_id"])
            now = _now_utc()
            with connection:
                connection.execute(
                    "UPDATE reply_suggestions SET status = ?, updated_at = ? WHERE id = ?",
                    (suggestion_status, now, suggestion_id),
                )
                connection.execute(
                    "UPDATE engagement_items SET status = ?, updated_at = ? WHERE id = ?",
                    (engagement_status, now, item["id"]),
                )
                self._append_audit(
                    connection,
                    suggestion_id=suggestion_id,
                    engagement_item_id=item["id"],
                    action=action,
                    previous_status=item["status"],
                    new_status=engagement_status,
                    reason=reason,
                    actor_type=actor_type,
                    created_at=now,
                )
            return self._get_suggestion(connection, suggestion_id)

    def _update_item_status(
        self,
        *,
        engagement_item_id: str,
        engagement_status: str,
        action: str,
        reason: str,
        actor_type: str,
        suggestion_id: str | None = None,
        suggestion_status: str | None = None,
    ) -> None:
        self._require_actor_type(actor_type)
        with self._connection() as connection:
            item = self._require_engagement_item(connection, engagement_item_id)
            if suggestion_id:
                suggestion = self._require_suggestion(connection, suggestion_id)
                if suggestion["engagement_item_id"] != engagement_item_id:
                    raise ReplyApprovalServiceError(
                        "Reply suggestion does not belong to this engagement item.",
                        ["reply_suggestion_item_mismatch"],
                    )
            now = _now_utc()
            with connection:
                if suggestion_id and suggestion_status:
                    connection.execute(
                        "UPDATE reply_suggestions SET status = ?, updated_at = ? WHERE id = ?",
                        (suggestion_status, now, suggestion_id),
                    )
                connection.execute(
                    "UPDATE engagement_items SET status = ?, updated_at = ? WHERE id = ?",
                    (engagement_status, now, engagement_item_id),
                )
                self._append_audit(
                    connection,
                    suggestion_id=suggestion_id,
                    engagement_item_id=engagement_item_id,
                    action=action,
                    previous_status=item["status"],
                    new_status=engagement_status,
                    reason=reason,
                    actor_type=actor_type,
                    created_at=now,
                )

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        *,
        suggestion_id: str | None,
        engagement_item_id: str,
        action: str,
        previous_status: str | None,
        new_status: str,
        reason: str | None,
        actor_type: str,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO reply_approvals (
              id, reply_suggestion_id, engagement_item_id, action,
              previous_status, new_status, reason, actor_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                suggestion_id,
                engagement_item_id,
                action,
                previous_status,
                new_status,
                reason,
                actor_type,
                created_at,
            ),
        )

    @staticmethod
    def _require_actor_type(actor_type: str) -> None:
        if actor_type not in REPLY_APPROVAL_ACTOR_TYPES:
            raise ReplyApprovalServiceError(
                f"actor_type must be one of: {', '.join(REPLY_APPROVAL_ACTOR_TYPES)}.",
                ["invalid_actor_type"],
            )

    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)

    @staticmethod
    def _require_suggestion(
        connection: sqlite3.Connection,
        suggestion_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM reply_suggestions WHERE id = ?",
            (suggestion_id,),
        ).fetchone()
        if not row:
            raise ReplyApprovalServiceError(
                f"Reply suggestion {suggestion_id!r} does not exist.",
                ["reply_suggestion_not_found"],
            )
        return row

    @staticmethod
    def _require_engagement_item(
        connection: sqlite3.Connection,
        engagement_item_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM engagement_items WHERE id = ?",
            (engagement_item_id,),
        ).fetchone()
        if not row:
            raise ReplyApprovalServiceError(
                f"Engagement item {engagement_item_id!r} does not exist.",
                ["engagement_item_not_found"],
            )
        return row

    @staticmethod
    def _get_suggestion(
        connection: sqlite3.Connection,
        suggestion_id: str,
    ) -> ReplySuggestion:
        return _row_to_suggestion(
            ReplyApprovalService._require_suggestion(connection, suggestion_id)
        )


def _row_to_suggestion(row: sqlite3.Row) -> ReplySuggestion:
    return ReplySuggestion(
        id=row["id"],
        engagementItemId=row["engagement_item_id"],
        brandProfileId=row["brand_profile_id"],
        suggestedReply=row["suggested_reply"],
        tone=row["tone"] or "helpful",
        confidence=row["confidence"],
        safetyFlags=_decode_json(row["safety_flags_json"], []),
        blockingFlags=_decode_json(row["blocking_flags_json"], []),
        safetyReview=_decode_json(row["safety_review_json"], []),
        recommendedAction=row["recommended_action"],
        needsHumanReview=bool(row["needs_human_review"]),
        reasonSummary=row["reasoning_summary"] or "",
        provider=row["provider"],
        promptTemplateId=row["prompt_template_id"],
        promptVersion=row["prompt_version"],
        status=row["status"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _row_to_approval(row: sqlite3.Row) -> ReplyApprovalRecord:
    return ReplyApprovalRecord(
        id=row["id"],
        replySuggestionId=row["reply_suggestion_id"],
        engagementItemId=row["engagement_item_id"],
        action=row["action"],
        previousStatus=row["previous_status"],
        newStatus=row["new_status"],
        reason=row["reason"],
        actorType=row["actor_type"],
        createdAt=row["created_at"],
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
