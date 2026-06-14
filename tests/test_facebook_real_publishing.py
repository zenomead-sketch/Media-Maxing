from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from scripts.db.init_db import initialize_database
from scripts.db.settings import update_app_settings
from scripts.db.social_connections import create_mock_social_account
from scripts.services.facebook_publishing import (
    FACEBOOK_PUBLISH_CONFIRMATION,
    FacebookPublishingError,
    FacebookPublishingService,
)
from scripts.services.platform_http_client import (
    NetworkSafetyMode,
    PlatformHttpClientConfig,
    PlatformHttpResponse,
)


def _json(value):
    return json.dumps(value, sort_keys=True)


class FacebookRealPublishingTest(unittest.TestCase):
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
                ("brand-facebook", "Facebook Test Business", "[]", "[]", "[]", "[]", "{}"),
            )
            connection.commit()
        return db_path

    def _ready_queue(
        self,
        db_path: Path,
        *,
        queue_status: str = "ready",
        preflight_status: str = "passed",
        account_status: str = "connected",
        token_mode: str = "insecure_dev_only",
    ) -> tuple[str, str, str, str]:
        account_id = create_mock_social_account(
            db_path,
            platform="facebook",
            display_name="Real Test Facebook Page",
            platform_account_id="fb-page-123",
            account_type="page",
            connection_status=account_status,
            granted_scopes=[
                "pages_show_list",
                "pages_manage_metadata",
                "pages_read_engagement",
                "pages_manage_posts",
            ],
            capabilities={"realPublishingEnabled": True},
            account_id="acct-facebook-real",
            now="2026-06-14T12:00:00Z",
        )
        draft_id = "draft-facebook-real"
        scheduled_id = "scheduled-facebook-real"
        queue_id = "queue-facebook-real"
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO platform_tokens (
                  id, social_account_id, platform, token_type,
                  encrypted_access_token, encrypted_refresh_token,
                  access_token_expires_at, refresh_token_expires_at, scope,
                  token_version, encryption_status, created_at, updated_at
                ) VALUES (?, ?, 'facebook', 'page_access', ?, NULL, ?, NULL, ?, 1, ?, ?, ?)
                """,
                (
                    "token-facebook-real",
                    account_id,
                    None if token_mode == "placeholder_not_stored" else "facebook-page-token-must-not-leak",
                    "2099-06-14T12:00:00Z",
                    "pages_show_list pages_manage_metadata pages_read_engagement pages_manage_posts",
                    token_mode,
                    "2026-06-14T12:00:00Z",
                    "2026-06-14T12:00:00Z",
                ),
            )
            connection.execute(
                """
                INSERT INTO generated_posts (
                  id, brand_profile_id, platform, caption, approval_status,
                  safety_flags_json, generation_provider
                ) VALUES (?, 'brand-facebook', 'facebook', ?, 'approved', '[]', 'mock')
                """,
                (draft_id, "Approved Facebook post ready for real publish."),
            )
            connection.execute(
                """
                INSERT INTO scheduled_posts (
                  id, generated_post_id, brand_profile_id, platform,
                  scheduled_for, timezone, status, caption_snapshot,
                  media_asset_ids_json, platform_account_id
                ) VALUES (?, ?, 'brand-facebook', 'facebook', ?, ?, 'queued', ?, '[]', ?)
                """,
                (
                    scheduled_id,
                    draft_id,
                    "2026-06-14T13:00:00Z",
                    "America/New_York",
                    "Approved Facebook post ready for real publish.",
                    "fb-page-123",
                ),
            )
            connection.execute(
                """
                INSERT INTO publish_queue_items (
                  id, scheduled_post_id, generated_post_id, brand_profile_id,
                  platform, queue_status, due_at, timezone, preflight_status,
                  preflight_errors_json, preflight_warnings_json
                ) VALUES (?, ?, ?, 'brand-facebook', 'facebook', ?, ?, ?, ?, '[]', '[]')
                """,
                (
                    queue_id,
                    scheduled_id,
                    draft_id,
                    queue_status,
                    "2026-06-14T13:00:00Z",
                    "America/New_York",
                    preflight_status,
                ),
            )
            connection.execute(
                "UPDATE scheduled_posts SET publish_queue_item_id = ? WHERE id = ?",
                (queue_id, scheduled_id),
            )
            connection.commit()
        return draft_id, scheduled_id, queue_id, account_id

    def _env(self, **overrides: str) -> dict[str, str]:
        values = {
            "APP_ENV": "development",
            "INTEGRATIONS_MODE": "real_oauth",
            "ENABLE_REAL_NETWORK_CALLS": "true",
            "ENABLE_REAL_OAUTH": "true",
            "ENABLE_REAL_PUBLISHING": "true",
            "TOKEN_STORAGE_MODE": "insecure_dev_only",
            "ALLOW_INSECURE_TOKEN_STORAGE": "true",
            "META_ENABLE_REAL_OAUTH": "true",
            "META_ENABLE_REAL_PUBLISHING": "true",
            "META_CLIENT_ID": "fake-client-id",
            "META_CLIENT_SECRET": "fake-client-secret",
            "META_REDIRECT_URI": "http://localhost:8000/api/connect/facebook/callback",
            "META_GRAPH_API_VERSION": "v25.0",
        }
        values.update(overrides)
        return values

    def test_confirmation_phrase_is_required_before_network_call(self):
        db_path = self._database()
        self._ready_queue(db_path)
        called = {"count": 0}

        def fail_if_called(request, timeout):
            called["count"] += 1
            raise AssertionError("network should not be called")

        with patch.dict(os.environ, self._env(), clear=True):
            with self.assertRaises(FacebookPublishingError) as error:
                FacebookPublishingService(
                    db_path,
                    http_client_config=PlatformHttpClientConfig(
                        provider="meta",
                        platform="facebook",
                        safetyMode=NetworkSafetyMode.ENABLED,
                        allowNetwork=True,
                        transport=fail_if_called,
                    ),
                ).publish_queue_item("queue-facebook-real", confirmation_phrase="publish")

        self.assertIn("confirmation_required", error.exception.error_codes)
        self.assertEqual(called["count"], 0)

    def test_emergency_pause_blocks_real_facebook_publish(self):
        db_path = self._database()
        self._ready_queue(db_path)
        update_app_settings(db_path, {"emergencyPauseEnabled": True})

        with patch.dict(os.environ, self._env(), clear=True):
            with self.assertRaises(FacebookPublishingError) as error:
                FacebookPublishingService(db_path).publish_queue_item(
                    "queue-facebook-real",
                    confirmation_phrase=FACEBOOK_PUBLISH_CONFIRMATION,
                )

        self.assertIn("emergency_pause_enabled", error.exception.error_codes)

    def test_placeholder_token_storage_blocks_real_facebook_publish(self):
        db_path = self._database()
        self._ready_queue(db_path, token_mode="placeholder_not_stored")

        with patch.dict(
            os.environ,
            self._env(TOKEN_STORAGE_MODE="placeholder_not_stored", ALLOW_INSECURE_TOKEN_STORAGE="false"),
            clear=True,
        ):
            with self.assertRaises(FacebookPublishingError) as error:
                FacebookPublishingService(db_path).publish_queue_item(
                    "queue-facebook-real",
                    confirmation_phrase=FACEBOOK_PUBLISH_CONFIRMATION,
                )

        self.assertIn("server_token_unavailable", error.exception.error_codes)

    def test_successful_real_facebook_publish_records_platform_api_without_leaking_token(self):
        db_path = self._database()
        draft_id, scheduled_id, queue_id, _account_id = self._ready_queue(db_path)
        captured = {}

        def fake_facebook_publish(request, timeout):
            captured["url"] = request.url
            captured["headers"] = dict(request.headers)
            captured["formBody"] = dict(request.formBody or {})
            return PlatformHttpResponse(
                ok=True,
                status=200,
                json={"id": "fb-post-999", "permalink_url": "https://facebook.com/fb-post-999"},
                text='{"id":"fb-post-999"}',
            )

        with patch.dict(os.environ, self._env(), clear=True):
            result = FacebookPublishingService(
                db_path,
                http_client_config=PlatformHttpClientConfig(
                    provider="meta",
                    platform="facebook",
                    safetyMode=NetworkSafetyMode.ENABLED,
                    allowNetwork=True,
                    transport=fake_facebook_publish,
                ),
            ).publish_queue_item(
                queue_id,
                confirmation_phrase=FACEBOOK_PUBLISH_CONFIRMATION,
                actor_label="local_owner",
            )

        self.assertTrue(result.success)
        self.assertEqual(result.queueStatus, "platform_published")
        self.assertEqual(result.externalPostId, "fb-post-999")
        self.assertIn("/fb-page-123/feed", captured["url"])
        self.assertEqual(
            captured["formBody"]["message"],
            "Approved Facebook post ready for real publish.",
        )

        with closing(sqlite3.connect(db_path)) as connection:
            queue_status, scheduled_status, readiness = connection.execute(
                """
                SELECT publish_queue_items.queue_status,
                       scheduled_posts.status,
                       generated_posts.publish_readiness_status
                FROM publish_queue_items
                JOIN scheduled_posts ON scheduled_posts.id = publish_queue_items.scheduled_post_id
                JOIN generated_posts ON generated_posts.id = publish_queue_items.generated_post_id
                WHERE publish_queue_items.id = ?
                """,
                (queue_id,),
            ).fetchone()
            published = connection.execute(
                "SELECT publish_mode, external_post_id, permalink FROM published_posts WHERE scheduled_post_id = ?",
                (scheduled_id,),
            ).fetchone()
            attempt = connection.execute(
                "SELECT attempt_type, attempt_status, provider_response_json FROM publish_attempts WHERE publish_queue_item_id = ?",
                (queue_id,),
            ).fetchone()
            audit = connection.execute(
                "SELECT action, changed_fields_json FROM approval_logs WHERE entity_id = ?",
                (scheduled_id,),
            ).fetchone()

        self.assertEqual((queue_status, scheduled_status, readiness), ("platform_published", "completed", "platform_published"))
        self.assertEqual(published, ("platform_api", "fb-post-999", "https://facebook.com/fb-post-999"))
        self.assertEqual((attempt[0], attempt[1]), ("future_real_publish", "succeeded"))
        serialized_attempt = attempt[2]
        self.assertNotIn("facebook-page-token-must-not-leak", serialized_attempt)
        self.assertIn("facebook_real_publish_completed", audit[0])
        self.assertEqual(draft_id, "draft-facebook-real")


if __name__ == "__main__":
    unittest.main()
