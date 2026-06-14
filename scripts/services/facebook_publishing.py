from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.connectors.registry import get_connector
from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings
from scripts.services.platform_http_client import (
    PlatformHttpClientConfig,
    redact_http_value,
)
from scripts.services.preflight import PreflightValidationService
from scripts.services.token_security import is_token_expired


FACEBOOK_PUBLISH_CONFIRMATION = "PUBLISH TO FACEBOOK"
FACEBOOK_REAL_PUBLISH_REQUIRED_SCOPES = {
    "pages_show_list",
    "pages_manage_metadata",
    "pages_read_engagement",
    "pages_manage_posts",
}


class FacebookPublishingError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class FacebookPublishResult:
    success: bool
    queueItemId: str
    scheduledPostId: str
    generatedPostId: str
    queueStatus: str
    scheduledPostStatus: str
    attemptId: str
    publishedPostId: str | None = None
    externalPostId: str | None = None
    permalink: str | None = None
    warnings: list[str] = field(default_factory=list)


class FacebookPublishingService:
    """Strictly gated real Facebook Page publishing.

    This service is intentionally one-platform and one-action: approved,
    preflighted Facebook text posts only. It does not publish images, videos,
    comments, DMs, or any other platform.
    """

    def __init__(
        self,
        database_path: str | Path | None = None,
        *,
        http_client_config: PlatformHttpClientConfig | None = None,
    ):
        self.database_path = initialize_database(resolve_database_path(database_path))
        self.http_client_config = http_client_config

    def publish_queue_item(
        self,
        queue_item_id: str,
        *,
        confirmation_phrase: str,
        actor_label: str = "local_user",
    ) -> FacebookPublishResult:
        if confirmation_phrase != FACEBOOK_PUBLISH_CONFIRMATION:
            raise FacebookPublishingError(
                f'Type "{FACEBOOK_PUBLISH_CONFIRMATION}" to publish to Facebook.',
                ["confirmation_required"],
            )

        queue_row = self._require_queue_row(queue_item_id)
        scheduled_row = self._require_scheduled_row(queue_row["scheduled_post_id"])
        draft_row = self._require_generated_post(queue_row["generated_post_id"])

        self._validate_environment()
        self._validate_local_state(queue_row, scheduled_row)
        preflight = PreflightValidationService(self.database_path).validate_queue_item(queue_item_id)
        if preflight.errors:
            raise FacebookPublishingError(
                "Facebook publish is blocked by preflight errors.",
                ["preflight_failed", *preflight.error_codes],
            )
        if preflight.accountErrors:
            raise FacebookPublishingError(
                "Facebook publish is blocked by account readiness errors.",
                ["account_not_ready"],
            )
        account_row = self._require_account(preflight.matchedSocialAccountId)
        self._validate_account(account_row)
        page_token = self._require_page_token(account_row["id"])

        now = _now_utc()
        attempt_id = str(uuid.uuid4())
        self._insert_attempt(
            attempt_id,
            queue_row,
            scheduled_row,
            status="started",
            started_at=now,
            finished_at=None,
            provider_response={},
        )
        try:
            action = get_connector("facebook").publishText(
                {
                    "pageId": account_row["platform_account_id"],
                    "message": scheduled_row["caption_snapshot"],
                    "pageAccessToken": page_token,
                },
                http_client_config=self.http_client_config,
            )
        except Exception as error:
            self._finish_failed_attempt(
                attempt_id,
                error_code="connector_error",
                error_message=str(error),
            )
            raise FacebookPublishingError(
                "Facebook connector failed safely before publishing could be confirmed.",
                ["connector_error"],
            ) from error

        if not action.success:
            self._finish_failed_attempt(
                attempt_id,
                error_code=action.status,
                error_message=action.message,
                provider_response=action.metadata,
            )
            raise FacebookPublishingError(
                action.message,
                [action.status],
            )

        external_post_id = _optional_text(action.metadata.get("externalPostId"))
        permalink = _optional_text(action.metadata.get("permalink"))
        published_post_id = f"published-facebook-{uuid.uuid4().hex[:12]}"
        self._record_success(
            queue_row,
            scheduled_row,
            draft_row,
            attempt_id=attempt_id,
            published_post_id=published_post_id,
            external_post_id=external_post_id,
            permalink=permalink,
            actor_label=actor_label,
            provider_response=action.metadata,
            completed_at=now,
        )
        return FacebookPublishResult(
            success=True,
            queueItemId=queue_row["id"],
            scheduledPostId=scheduled_row["id"],
            generatedPostId=draft_row["id"],
            queueStatus="platform_published",
            scheduledPostStatus="completed",
            attemptId=attempt_id,
            publishedPostId=published_post_id,
            externalPostId=external_post_id,
            permalink=permalink,
            warnings=[
                "facebook_text_only: Only Facebook Page text posting is implemented.",
                "no_auto_publish: This was triggered by explicit local confirmation.",
            ],
        )

    def _validate_environment(self) -> None:
        settings = load_app_settings(self.database_path)
        if settings.emergencyPauseEnabled:
            raise FacebookPublishingError(
                "Emergency pause blocks real Facebook publishing.",
                ["emergency_pause_enabled"],
            )
        env = os.environ
        required_truthy = {
            "ENABLE_REAL_PUBLISHING": env.get("ENABLE_REAL_PUBLISHING"),
            "META_ENABLE_REAL_PUBLISHING": env.get("META_ENABLE_REAL_PUBLISHING"),
            "ENABLE_REAL_NETWORK_CALLS": env.get("ENABLE_REAL_NETWORK_CALLS"),
        }
        missing_flags = [key for key, value in required_truthy.items() if not _truthy(value)]
        if missing_flags:
            raise FacebookPublishingError(
                "Real Facebook publishing is disabled by feature flags.",
                ["real_publishing_disabled", *missing_flags],
            )
        if (env.get("INTEGRATIONS_MODE") or "mock").strip().lower() != "real_oauth":
            raise FacebookPublishingError(
                "Real Facebook publishing requires INTEGRATIONS_MODE=real_oauth.",
                ["real_oauth_mode_required"],
            )

    def _validate_local_state(
        self,
        queue_row: sqlite3.Row,
        scheduled_row: sqlite3.Row,
    ) -> None:
        if queue_row["platform"] != "facebook" or scheduled_row["platform"] != "facebook":
            raise FacebookPublishingError(
                "Only Facebook queue items can use Facebook real publishing.",
                ["platform_not_facebook"],
            )
        if queue_row["queue_status"] != "ready":
            raise FacebookPublishingError(
                "Only ready queue items can be published to Facebook.",
                ["queue_not_ready"],
            )
        if queue_row["preflight_status"] not in {"passed", "warnings"}:
            raise FacebookPublishingError(
                "Facebook publishing requires passed or warning-only preflight.",
                ["preflight_not_ready"],
            )
        if scheduled_row["status"] not in {"queued", "scheduled"}:
            raise FacebookPublishingError(
                "Scheduled post must be queued or scheduled before publishing.",
                ["scheduled_post_not_publishable"],
            )
        if not str(scheduled_row["caption_snapshot"] or "").strip():
            raise FacebookPublishingError(
                "Facebook publishing requires a caption snapshot.",
                ["missing_caption_snapshot"],
            )

    def _validate_account(self, account_row: sqlite3.Row) -> None:
        if account_row["platform"] != "facebook":
            raise FacebookPublishingError("Matched account is not Facebook.", ["account_platform_mismatch"])
        if account_row["connection_status"] != "connected":
            raise FacebookPublishingError(
                "Facebook account must be connected before real publishing.",
                ["account_not_connected"],
            )
        if account_row["requires_reauth"]:
            raise FacebookPublishingError(
                "Facebook account requires reauthorization before publishing.",
                ["account_requires_reauth"],
            )
        if not _optional_text(account_row["platform_account_id"]):
            raise FacebookPublishingError(
                "Facebook Page ID is missing.",
                ["missing_facebook_page_id"],
            )
        granted = set(_decode_json(account_row["granted_scopes_json"], []))
        missing = sorted(FACEBOOK_REAL_PUBLISH_REQUIRED_SCOPES - granted)
        if missing:
            raise FacebookPublishingError(
                "Facebook account is missing scopes required for real publishing.",
                ["missing_required_scopes", *missing],
            )

    def _require_page_token(self, account_id: str) -> str:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT *
                FROM platform_tokens
                WHERE social_account_id = ?
                  AND platform = 'facebook'
                  AND revoked_at IS NULL
                ORDER BY
                  CASE token_type WHEN 'page_access' THEN 0 ELSE 1 END,
                  created_at DESC
                LIMIT 1
                """,
                (account_id,),
            ).fetchone()
        if row is None:
            raise FacebookPublishingError(
                "No Facebook Page token metadata exists.",
                ["server_token_unavailable"],
            )
        if row["encryption_status"] != "insecure_dev_only":
            raise FacebookPublishingError(
                "Secure token retrieval is not available yet. Placeholder token storage blocks real publishing.",
                ["server_token_unavailable"],
            )
        if os.environ.get("APP_ENV") != "development" or not _truthy(os.environ.get("ALLOW_INSECURE_TOKEN_STORAGE")):
            raise FacebookPublishingError(
                "Insecure token retrieval is allowed only in explicit local development mode.",
                ["insecure_token_mode_blocked"],
            )
        if is_token_expired(row["access_token_expires_at"]):
            raise FacebookPublishingError(
                "Facebook Page token is expired.",
                ["token_expired"],
            )
        token = _optional_text(row["encrypted_access_token"])
        if not token:
            raise FacebookPublishingError(
                "Facebook Page token value is not available server-side.",
                ["server_token_unavailable"],
            )
        return token

    def _insert_attempt(
        self,
        attempt_id: str,
        queue_row: sqlite3.Row,
        scheduled_row: sqlite3.Row,
        *,
        status: str,
        started_at: str,
        finished_at: str | None,
        provider_response: dict[str, Any],
    ) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO publish_attempts (
                  id, publish_queue_item_id, scheduled_post_id, platform,
                  attempt_type, attempt_status, started_at, finished_at,
                  provider_response_json, created_at
                ) VALUES (?, ?, ?, 'facebook', 'future_real_publish', ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    queue_row["id"],
                    scheduled_row["id"],
                    status,
                    started_at,
                    finished_at,
                    _safe_json(provider_response),
                    started_at,
                ),
            )
            connection.commit()

    def _finish_failed_attempt(
        self,
        attempt_id: str,
        *,
        error_code: str,
        error_message: str,
        provider_response: dict[str, Any] | None = None,
    ) -> None:
        now = _now_utc()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                UPDATE publish_attempts
                SET attempt_status = 'failed',
                    finished_at = ?,
                    error_code = ?,
                    error_message = ?,
                    provider_response_json = ?
                WHERE id = ?
                """,
                (
                    now,
                    error_code,
                    error_message,
                    _safe_json(provider_response or {}),
                    attempt_id,
                ),
            )
            connection.commit()

    def _record_success(
        self,
        queue_row: sqlite3.Row,
        scheduled_row: sqlite3.Row,
        draft_row: sqlite3.Row,
        *,
        attempt_id: str,
        published_post_id: str,
        external_post_id: str | None,
        permalink: str | None,
        actor_label: str,
        provider_response: dict[str, Any],
        completed_at: str,
    ) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN")
            connection.execute(
                "UPDATE publish_queue_items SET queue_status = 'platform_published', updated_at = ? WHERE id = ?",
                (completed_at, queue_row["id"]),
            )
            connection.execute(
                "UPDATE scheduled_posts SET status = 'completed', updated_at = ? WHERE id = ?",
                (completed_at, scheduled_row["id"]),
            )
            connection.execute(
                "UPDATE generated_posts SET publish_readiness_status = 'platform_published', updated_at = ? WHERE id = ?",
                (completed_at, draft_row["id"]),
            )
            connection.execute(
                """
                INSERT INTO published_posts (
                  id, scheduled_post_id, generated_post_id, platform, publish_mode,
                  external_post_id, permalink, published_at, metadata_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, 'facebook', 'platform_api', ?, ?, ?, ?, ?, ?)
                """,
                (
                    published_post_id,
                    scheduled_row["id"],
                    draft_row["id"],
                    external_post_id,
                    permalink,
                    completed_at,
                    _safe_json(
                        {
                            "source": "facebook_publishing_service",
                            "attemptId": attempt_id,
                            "pageId": scheduled_row["platform_account_id"],
                            "realPublishing": True,
                            "autoPublish": False,
                        }
                    ),
                    completed_at,
                    completed_at,
                ),
            )
            connection.execute(
                """
                UPDATE publish_attempts
                SET attempt_status = 'succeeded',
                    finished_at = ?,
                    provider_response_json = ?
                WHERE id = ?
                """,
                (
                    completed_at,
                    _safe_json(
                        {
                            "source": "facebook_connector",
                            "externalPostId": external_post_id,
                            "permalink": permalink,
                            "providerResponse": provider_response.get("providerResponse"),
                        }
                    ),
                    attempt_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO approval_logs (
                  id, entity_type, entity_id, action, actor_label,
                  notes, changed_fields_json, created_at
                ) VALUES (?, 'scheduled_post', ?, 'facebook_real_publish_completed', ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    scheduled_row["id"],
                    actor_label,
                    "Facebook Page text post published after explicit local confirmation.",
                    _safe_json(
                        {
                            "publishQueueItemId": queue_row["id"],
                            "previousQueueStatus": queue_row["queue_status"],
                            "queueStatus": "platform_published",
                            "scheduledPostStatus": "completed",
                            "publishedPostId": published_post_id,
                            "externalPostId": external_post_id,
                        }
                    ),
                    completed_at,
                ),
            )
            connection.commit()

    def _require_queue_row(self, queue_item_id: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM publish_queue_items WHERE id = ?", (queue_item_id,)).fetchone()
        if row is None:
            raise FacebookPublishingError("Publish queue item was not found.", ["queue_item_not_found"])
        return row

    def _require_scheduled_row(self, scheduled_post_id: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM scheduled_posts WHERE id = ?", (scheduled_post_id,)).fetchone()
        if row is None:
            raise FacebookPublishingError("Scheduled post was not found.", ["scheduled_post_not_found"])
        return row

    def _require_generated_post(self, generated_post_id: str) -> sqlite3.Row:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM generated_posts WHERE id = ?", (generated_post_id,)).fetchone()
        if row is None:
            raise FacebookPublishingError("Generated post was not found.", ["generated_post_not_found"])
        return row

    def _require_account(self, account_id: str | None) -> sqlite3.Row:
        if not account_id:
            raise FacebookPublishingError("No Facebook account matched preflight.", ["missing_facebook_account"])
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM social_accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise FacebookPublishingError("Matched Facebook account was not found.", ["facebook_account_not_found"])
        return row


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_json(value: Any) -> str:
    return json.dumps(redact_http_value(value).value, sort_keys=True, separators=(",", ":"))


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
