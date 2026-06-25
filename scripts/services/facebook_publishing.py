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
from scripts.connectors.meta.facebook import GUARDED_FACEBOOK_PUBLISH_CONTEXT
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
FACEBOOK_SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
FACEBOOK_MAX_IMAGE_BYTES = 25 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[2]


class FacebookPublishingError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class FacebookPublishMedia:
    mediaAssetId: str
    path: Path
    filename: str
    contentType: str
    content: bytes


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

    This service is intentionally one-platform and narrow: approved,
    preflighted Facebook Page text posts or single-image photo posts only. It
    does not publish videos, albums, comments, DMs, or any other platform.
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
        publish_media = self._resolve_publish_media(scheduled_row)

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
            if publish_media:
                action = get_connector("facebook").publishImage(
                    {
                        "pageId": account_row["platform_account_id"],
                        "message": scheduled_row["caption_snapshot"],
                        "pageAccessToken": page_token,
                        "imageBytes": publish_media.content,
                        "filename": publish_media.filename,
                        "contentType": publish_media.contentType,
                        "guardedServiceContext": GUARDED_FACEBOOK_PUBLISH_CONTEXT,
                    },
                    http_client_config=self.http_client_config,
                )
                publish_kind = "facebook_photo"
            else:
                action = get_connector("facebook").publishText(
                    {
                        "pageId": account_row["platform_account_id"],
                        "message": scheduled_row["caption_snapshot"],
                        "pageAccessToken": page_token,
                        "guardedServiceContext": GUARDED_FACEBOOK_PUBLISH_CONTEXT,
                    },
                    http_client_config=self.http_client_config,
                )
                publish_kind = "facebook_text"
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
            publish_kind=publish_kind,
            media_asset_ids=[publish_media.mediaAssetId] if publish_media else [],
            completed_at=now,
        )
        warnings = [
            "no_auto_publish: This was triggered by explicit local confirmation.",
        ]
        if publish_media:
            warnings.append(
                "facebook_single_image: One linked local image was uploaded with the generated caption."
            )
        else:
            warnings.append("facebook_text_only: No linked image was included in this publish.")
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
            warnings=warnings,
        )

    def get_readiness_summary(self) -> dict[str, Any]:
        """Return a token-safe checklist for owner-facing Facebook setup.

        This method performs local database and environment checks only. It
        never calls Meta, never returns token values, and never attempts to
        publish. The browser uses this to explain what is blocking the guarded
        Facebook Page text/single-image path.
        """
        steps: list[dict[str, Any]] = []
        blocker_codes: list[str] = []
        warning_codes: list[str] = []

        def add_step(
            step_id: str,
            label: str,
            status: str,
            summary: str,
            *,
            action_label: str,
            href: str,
            codes: list[str] | None = None,
        ) -> None:
            safe_codes = codes or []
            if status == "blocked":
                blocker_codes.extend(safe_codes)
            elif status == "warning":
                warning_codes.extend(safe_codes)
            steps.append(
                {
                    "id": step_id,
                    "label": label,
                    "status": status,
                    "summary": summary,
                    "actionLabel": action_label,
                    "href": href,
                    "codes": safe_codes,
                }
            )

        settings = load_app_settings(self.database_path)
        if settings.emergencyPauseEnabled:
            add_step(
                "emergency_pause",
                "Emergency pause",
                "blocked",
                "Emergency pause is on, so Facebook posting is blocked.",
                action_label="Open Safety Center",
                href="#safety",
                codes=["emergency_pause_enabled"],
            )
        else:
            add_step(
                "emergency_pause",
                "Emergency pause",
                "ready",
                "Emergency pause is off.",
                action_label="Open Safety Center",
                href="#safety",
            )

        env = os.environ
        required_truthy = {
            "ENABLE_REAL_PUBLISHING": env.get("ENABLE_REAL_PUBLISHING"),
            "META_ENABLE_REAL_PUBLISHING": env.get("META_ENABLE_REAL_PUBLISHING"),
            "ENABLE_REAL_NETWORK_CALLS": env.get("ENABLE_REAL_NETWORK_CALLS"),
        }
        missing_flags = [key for key, value in required_truthy.items() if not _truthy(value)]
        integration_mode = (env.get("INTEGRATIONS_MODE") or "mock").strip().lower()
        if integration_mode != "real_oauth":
            missing_flags.append("INTEGRATIONS_MODE=real_oauth")
        if missing_flags:
            add_step(
                "publishing_flags",
                "Facebook posting flags",
                "blocked",
                "Real Facebook posting is still disabled in local environment flags.",
                action_label="Open setup wizard",
                href="#setup",
                codes=["real_publishing_disabled", *missing_flags],
            )
        else:
            add_step(
                "publishing_flags",
                "Facebook posting flags",
                "ready",
                "Required local real OAuth/network/publishing flags are enabled.",
                action_label="Open setup wizard",
                href="#setup",
            )

        account_row = self._best_facebook_account()
        if account_row is None:
            add_step(
                "facebook_account",
                "Facebook Page account",
                "blocked",
                "No connected Facebook Page account was found.",
                action_label="Open Connected Accounts",
                href="#connected",
                codes=["missing_facebook_account"],
            )
        else:
            account_status = str(account_row["connection_status"] or "unknown")
            requires_reauth = bool(account_row["requires_reauth"])
            if account_status != "connected" or requires_reauth:
                add_step(
                    "facebook_account",
                    "Facebook Page account",
                    "blocked",
                    f"Facebook account status is {account_status}; reconnect before posting.",
                    action_label="Reconnect Facebook",
                    href="#connected",
                    codes=["account_not_connected" if account_status != "connected" else "account_requires_reauth"],
                )
            elif not _optional_text(account_row["platform_account_id"]):
                add_step(
                    "facebook_account",
                    "Facebook Page account",
                    "blocked",
                    "The connected Facebook account is missing a Page ID.",
                    action_label="Reconnect Facebook",
                    href="#connected",
                    codes=["missing_facebook_page_id"],
                )
            elif _looks_like_mock_facebook_account(account_row):
                add_step(
                    "facebook_account",
                    "Facebook Page account",
                    "blocked",
                    "This looks like a demo/mock Facebook Page account. Connect a real Facebook Page before posting.",
                    action_label="Connect real Facebook",
                    href="#connected",
                    codes=["mock_facebook_account"],
                )
            else:
                add_step(
                    "facebook_account",
                    "Facebook Page account",
                    "ready",
                    f"Connected to {account_row['display_name'] or 'Facebook Page'}.",
                    action_label="Open Connected Accounts",
                    href="#connected",
                )

            granted = set(_decode_json(account_row["granted_scopes_json"], []))
            missing_scopes = sorted(FACEBOOK_REAL_PUBLISH_REQUIRED_SCOPES - granted)
            if missing_scopes:
                add_step(
                    "page_permissions",
                    "Page permissions",
                    "blocked",
                    "Facebook connection is missing required Page permissions: "
                    + ", ".join(missing_scopes),
                    action_label="Reconnect Facebook",
                    href="#connected",
                    codes=["missing_required_scopes", *missing_scopes],
                )
            else:
                add_step(
                    "page_permissions",
                    "Page permissions",
                    "ready",
                    "Required Facebook Page posting permissions are present.",
                    action_label="Open Connected Accounts",
                    href="#connected",
                )

            token_step = self._page_token_readiness_step(str(account_row["id"]))
            add_step(**token_step)

        ready_queue_count = self._ready_facebook_queue_count()
        if ready_queue_count:
            add_step(
                "ready_queue_item",
                "Ready Facebook post",
                "ready",
                f"{ready_queue_count} Facebook queue item(s) are ready for the guarded publish button.",
                action_label="Open Publish Queue",
                href="#queue",
            )
        else:
            add_step(
                "ready_queue_item",
                "Ready Facebook post",
                "blocked",
                "No ready Facebook queue item exists yet. Create content, approve it, schedule it, then run preflight.",
                action_label="Create or review posts",
                href="#generate",
                codes=["no_ready_facebook_queue_item"],
            )

        add_step(
            "typed_confirmation",
            "Final confirmation",
            "ready",
            f'The app still requires typing "{FACEBOOK_PUBLISH_CONFIRMATION}" before creating a Facebook Page post.',
            action_label="Open Publish Queue",
            href="#queue",
        )

        deduped_blockers = _dedupe(blocker_codes)
        deduped_warnings = _dedupe(warning_codes)
        next_action = next(
            (
                {
                    "label": step["actionLabel"],
                    "href": step["href"],
                    "summary": step["summary"],
                }
                for step in steps
                if step["status"] == "blocked"
            ),
            {
                "label": "Open Publish Queue",
                "href": "#queue",
                "summary": "A ready Facebook post can use the guarded publish button after typed confirmation.",
            },
        )
        return {
            "summaryId": "facebook_posting_steps_v1",
            "ready": not deduped_blockers,
            "status": "ready" if not deduped_blockers else "blocked",
            "headline": "Facebook posting setup",
            "summary": (
                "Ready to post to Facebook with the guarded local API."
                if not deduped_blockers
                else "Facebook posting is not ready yet. Fix the blocked steps below."
            ),
            "steps": steps,
            "blockerCodes": deduped_blockers,
            "warningCodes": deduped_warnings,
            "readyQueueItemCount": ready_queue_count,
            "confirmationPhrase": FACEBOOK_PUBLISH_CONFIRMATION,
            "nextAction": next_action,
            "safetyNote": "No autonomous posting. Facebook posting still requires a ready queue item and typed owner confirmation.",
        }

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
        if _looks_like_mock_facebook_account(account_row):
            raise FacebookPublishingError(
                "Demo/mock Facebook accounts cannot use real publishing.",
                ["mock_facebook_account"],
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

    def _resolve_publish_media(self, scheduled_row: sqlite3.Row) -> FacebookPublishMedia | None:
        media_ids = _decode_json(
            scheduled_row["media_asset_ids_json"] or scheduled_row["media_snapshot_json"],
            [],
        )
        if not media_ids:
            return None
        media_ids = [str(media_id).strip() for media_id in media_ids if str(media_id).strip()]
        if not media_ids:
            return None
        if len(media_ids) > 1:
            raise FacebookPublishingError(
                "Facebook real publishing currently supports one linked image per post. Use Manual Export for multi-image posts.",
                ["facebook_multiple_media_not_supported"],
            )
        media_id = media_ids[0]
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, media_type, original_path, file_name, mime_type, file_size_bytes
                FROM media_assets
                WHERE id = ?
                """,
                (media_id,),
            ).fetchone()
        if row is None:
            raise FacebookPublishingError(
                "Linked media asset was not found.",
                ["media_asset_not_found"],
            )
        mime_type = str(row["mime_type"] or "").strip().lower()
        if row["media_type"] != "image" or not mime_type.startswith("image/"):
            raise FacebookPublishingError(
                "Facebook real publishing currently supports image media only. Use Manual Export for videos or other files.",
                ["facebook_media_type_not_supported"],
            )
        if mime_type not in FACEBOOK_SUPPORTED_IMAGE_MIME_TYPES:
            raise FacebookPublishingError(
                "Facebook real publishing does not support this local image type yet.",
                ["facebook_image_mime_not_supported"],
            )
        source_path = _resolve_local_path(row["original_path"])
        if not source_path.exists() or not source_path.is_file():
            raise FacebookPublishingError(
                "Linked media file is missing from local storage.",
                ["media_file_missing"],
            )
        size_bytes = source_path.stat().st_size
        if size_bytes <= 0:
            raise FacebookPublishingError(
                "Linked media file is empty.",
                ["media_file_empty"],
            )
        if size_bytes > FACEBOOK_MAX_IMAGE_BYTES:
            raise FacebookPublishingError(
                "Linked image is too large for the current guarded Facebook upload path.",
                ["facebook_image_too_large"],
            )
        return FacebookPublishMedia(
            mediaAssetId=media_id,
            path=source_path,
            filename=str(row["file_name"] or source_path.name),
            contentType=mime_type,
            content=source_path.read_bytes(),
        )

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
        publish_kind: str,
        media_asset_ids: list[str],
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
                            "publishKind": publish_kind,
                            "mediaAssetIds": media_asset_ids,
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
                            "publishKind": publish_kind,
                            "mediaAssetIds": media_asset_ids,
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
                    "Facebook Page post published after explicit local confirmation.",
                    _safe_json(
                        {
                            "publishQueueItemId": queue_row["id"],
                            "previousQueueStatus": queue_row["queue_status"],
                            "queueStatus": "platform_published",
                            "scheduledPostStatus": "completed",
                            "publishKind": publish_kind,
                            "mediaAssetIds": media_asset_ids,
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

    def _best_facebook_account(self) -> sqlite3.Row | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            return connection.execute(
                """
                SELECT *
                FROM social_accounts
                WHERE platform = 'facebook'
                ORDER BY
                  CASE connection_status
                    WHEN 'connected' THEN 0
                    WHEN 'limited' THEN 1
                    WHEN 'requires_reauth' THEN 2
                    WHEN 'expired' THEN 3
                    WHEN 'revoked' THEN 4
                    ELSE 5
                  END,
                  last_validated_at DESC,
                  created_at DESC
                LIMIT 1
                """
            ).fetchone()

    def _page_token_readiness_step(self, account_id: str) -> dict[str, Any]:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT id, token_type, encrypted_access_token, access_token_expires_at,
                       encryption_status, revoked_at
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
            return {
                "step_id": "page_token",
                "label": "Server-side Page token",
                "status": "blocked",
                "summary": "No server-side Facebook Page token metadata exists.",
                "action_label": "Reconnect Facebook",
                "href": "#connected",
                "codes": ["server_token_unavailable"],
            }
        if row["encryption_status"] != "insecure_dev_only":
            return {
                "step_id": "page_token",
                "label": "Server-side Page token",
                "status": "blocked",
                "summary": "Token storage is placeholder-only. Reconnect in explicit local development token mode.",
                "action_label": "Reconnect Facebook",
                "href": "#connected",
                "codes": ["server_token_unavailable"],
            }
        if os.environ.get("APP_ENV") != "development" or not _truthy(os.environ.get("ALLOW_INSECURE_TOKEN_STORAGE")):
            return {
                "step_id": "page_token",
                "label": "Server-side Page token",
                "status": "blocked",
                "summary": "Local development token retrieval is not explicitly enabled.",
                "action_label": "Open setup wizard",
                "href": "#setup",
                "codes": ["insecure_token_mode_blocked"],
            }
        if is_token_expired(row["access_token_expires_at"]):
            return {
                "step_id": "page_token",
                "label": "Server-side Page token",
                "status": "blocked",
                "summary": "The stored Facebook Page token is expired.",
                "action_label": "Reconnect Facebook",
                "href": "#connected",
                "codes": ["token_expired"],
            }
        if not _optional_text(row["encrypted_access_token"]):
            return {
                "step_id": "page_token",
                "label": "Server-side Page token",
                "status": "blocked",
                "summary": "The Facebook Page token value is unavailable server-side.",
                "action_label": "Reconnect Facebook",
                "href": "#connected",
                "codes": ["server_token_unavailable"],
            }
        return {
            "step_id": "page_token",
            "label": "Server-side Page token",
            "status": "ready",
            "summary": "A local development Page token is available server-side. Token value is hidden.",
            "action_label": "Open Connected Accounts",
            "href": "#connected",
        }

    def _ready_facebook_queue_count(self) -> int:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM publish_queue_items
                WHERE platform = 'facebook'
                  AND queue_status = 'ready'
                  AND preflight_status IN ('passed', 'warnings')
                """
            ).fetchone()
        return int(row[0] if row else 0)


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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _looks_like_mock_facebook_account(account_row: sqlite3.Row) -> bool:
    values = [
        account_row["id"],
        account_row["platform_account_id"],
        account_row["display_name"],
    ]
    normalized = " ".join(str(value or "").lower() for value in values)
    return "mock" in normalized or "demo" in normalized


def _resolve_local_path(path_value: str | None) -> Path:
    if not path_value:
        return REPO_ROOT / "__missing__"
    path = Path(path_value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()
