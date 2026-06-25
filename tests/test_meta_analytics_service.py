from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from scripts.db.init_db import initialize_database
from scripts.db.social_connections import create_mock_social_account
from scripts.services.meta_analytics import MetaAnalyticsError, MetaAnalyticsService
from scripts.services.platform_http_client import (
    NetworkSafetyMode,
    PlatformHttpClientConfig,
    PlatformHttpResponse,
)


class MetaAnalyticsServiceTest(unittest.TestCase):
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
                (
                    "brand-meta-analytics",
                    "Meta Analytics Test Business",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "{}",
                ),
            )
            connection.commit()
        return db_path

    def _account_with_dev_token(
        self,
        db_path: Path,
        *,
        platform: str,
        platform_account_id: str,
        granted_scopes: list[str],
        token: str = "meta-dev-token-must-not-leak",
    ) -> str:
        account_id = create_mock_social_account(
            db_path,
            platform=platform,
            display_name=f"Real {platform.title()} Account",
            platform_account_id=platform_account_id,
            brand_profile_id="brand-meta-analytics",
            account_type="page" if platform == "facebook" else "business",
            connection_status="connected",
            granted_scopes=granted_scopes,
            account_id=f"acct-{platform}-analytics",
            now="2026-06-23T12:00:00Z",
        )
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO platform_tokens (
                  id, social_account_id, platform, token_type,
                  encrypted_access_token, encrypted_refresh_token,
                  access_token_expires_at, refresh_token_expires_at, scope,
                  token_version, encryption_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, ?, 1, 'insecure_dev_only', ?, ?)
                """,
                (
                    f"token-{platform}-analytics",
                    account_id,
                    platform,
                    "page_access" if platform == "facebook" else "oauth_access",
                    token,
                    "2099-06-23T12:00:00Z",
                    " ".join(granted_scopes),
                    "2026-06-23T12:00:00Z",
                    "2026-06-23T12:00:00Z",
                ),
            )
            connection.commit()
        return account_id

    def _env(self):
        return patch.dict(
            "os.environ",
            {
                "APP_ENV": "development",
                "ALLOW_INSECURE_TOKEN_STORAGE": "true",
                "INTEGRATIONS_MODE": "real_oauth",
                "ENABLE_REAL_OAUTH": "true",
                "ENABLE_REAL_NETWORK_CALLS": "true",
                "META_ENABLE_REAL_OAUTH": "true",
                "META_CLIENT_ID": "meta-client-id",
                "META_CLIENT_SECRET": "meta-client-secret-must-not-leak",
                "META_REDIRECT_URI": "http://127.0.0.1:8000/api/connect/facebook/callback",
                "META_GRAPH_API_VERSION": "v20.0",
            },
            clear=False,
        )

    def test_facebook_sync_stores_platform_api_snapshot_with_media(self):
        db_path = self._database()
        self._account_with_dev_token(
            db_path,
            platform="facebook",
            platform_account_id="fb-page-123",
            granted_scopes=["pages_show_list", "pages_read_engagement"],
        )

        def fake_meta(request, timeout):
            self.assertEqual(str(request.method), "GET")
            self.assertIn("/fb-page-123/posts", request.url)
            return PlatformHttpResponse(
                ok=True,
                status=200,
                json={
                    "data": [
                        {
                            "id": "fb-post-1",
                            "message": "Real Facebook post caption.",
                            "created_time": "2026-06-20T14:00:00+0000",
                            "permalink_url": "https://facebook.com/page/posts/fb-post-1",
                            "full_picture": "https://cdn.example.com/facebook-photo.jpg",
                            "shares": {"count": 3},
                            "comments": {"summary": {"total_count": 4}},
                            "reactions": {"summary": {"total_count": 21}},
                            "insights": {
                                "data": [
                                    {"name": "post_impressions", "values": [{"value": 1200}]},
                                    {"name": "post_impressions_unique", "values": [{"value": 900}]},
                                    {"name": "post_engaged_users", "values": [{"value": 140}]},
                                    {"name": "post_clicks", "values": [{"value": 17}]},
                                    {"name": "post_video_views", "values": [{"value": 0}]},
                                ]
                            },
                        }
                    ]
                },
            )

        with self._env():
            result = MetaAnalyticsService(
                db_path,
                http_client_config=PlatformHttpClientConfig(
                    provider="meta",
                    platform="facebook",
                    safetyMode=NetworkSafetyMode.ENABLED,
                    allowNetwork=True,
                    transport=fake_meta,
                ),
            ).sync(platforms=["facebook"], limit=5)

        self.assertEqual(result.createdCount, 1)
        self.assertEqual(result.errorCount, 0)

        with closing(sqlite3.connect(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            snapshot = connection.execute(
                "SELECT * FROM analytics_snapshots WHERE source = 'platform_api'"
            ).fetchone()
            published = connection.execute(
                "SELECT * FROM published_posts WHERE external_post_id = 'fb-post-1'"
            ).fetchone()
            import_row = connection.execute(
                "SELECT import_type, status FROM analytics_imports WHERE id = ?",
                (result.importId,),
            ).fetchone()

        self.assertIsNotNone(snapshot)
        self.assertIsNotNone(published)
        self.assertEqual(import_row["import_type"], "platform_sync")
        self.assertEqual(import_row["status"], "completed")
        self.assertEqual(snapshot["published_post_id"], published["id"])
        self.assertEqual(snapshot["platform"], "facebook")
        self.assertEqual(snapshot["impressions"], 1200)
        raw_metrics = json.loads(snapshot["raw_metrics_json"])
        self.assertEqual(raw_metrics["externalPostId"], "fb-post-1")
        self.assertEqual(raw_metrics["caption"], "Real Facebook post caption.")
        self.assertEqual(raw_metrics["media"][0]["url"], "https://cdn.example.com/facebook-photo.jpg")
        self.assertNotIn("meta-dev-token-must-not-leak", snapshot["raw_metrics_json"])
        self.assertNotIn("meta-client-secret-must-not-leak", snapshot["raw_metrics_json"])

    def test_instagram_sync_stores_media_children_and_insights(self):
        db_path = self._database()
        self._account_with_dev_token(
            db_path,
            platform="instagram",
            platform_account_id="ig-user-123",
            granted_scopes=["instagram_basic", "instagram_manage_insights"],
        )

        def fake_meta(request, timeout):
            self.assertIn("/ig-user-123/media", request.url)
            return PlatformHttpResponse(
                ok=True,
                status=200,
                json={
                    "data": [
                        {
                            "id": "ig-media-1",
                            "caption": "Real Instagram caption.",
                            "media_type": "CAROUSEL_ALBUM",
                            "media_url": "https://cdn.example.com/ig-cover.jpg",
                            "permalink": "https://instagram.com/p/ig-media-1/",
                            "timestamp": "2026-06-21T15:30:00+0000",
                            "like_count": 45,
                            "comments_count": 6,
                            "children": {
                                "data": [
                                    {
                                        "media_type": "IMAGE",
                                        "media_url": "https://cdn.example.com/ig-child.jpg",
                                    }
                                ]
                            },
                            "insights": {
                                "data": [
                                    {"name": "views", "values": [{"value": 800}]},
                                    {"name": "reach", "values": [{"value": 620}]},
                                    {"name": "likes", "values": [{"value": 47}]},
                                    {"name": "comments", "values": [{"value": 7}]},
                                    {"name": "saved", "values": [{"value": 12}]},
                                    {"name": "shares", "values": [{"value": 5}]},
                                ]
                            },
                        }
                    ]
                },
            )

        with self._env():
            result = MetaAnalyticsService(
                db_path,
                http_client_config=PlatformHttpClientConfig(
                    provider="meta",
                    platform="instagram",
                    safetyMode=NetworkSafetyMode.ENABLED,
                    allowNetwork=True,
                    transport=fake_meta,
                ),
            ).sync(platforms=["instagram"], limit=5)

        self.assertEqual(result.createdCount, 1)
        with closing(sqlite3.connect(db_path)) as connection:
            connection.row_factory = sqlite3.Row
            snapshot = connection.execute(
                "SELECT * FROM analytics_snapshots WHERE platform = 'instagram'"
            ).fetchone()
        raw_metrics = json.loads(snapshot["raw_metrics_json"])
        self.assertEqual(snapshot["views"], 800)
        self.assertEqual(snapshot["reach"], 620)
        self.assertEqual(snapshot["likes"], 47)
        self.assertEqual(snapshot["comments"], 7)
        self.assertEqual(len(raw_metrics["media"]), 2)
        self.assertEqual(raw_metrics["media"][1]["url"], "https://cdn.example.com/ig-child.jpg")

    def test_multi_platform_sync_uses_nullable_import_platform(self):
        db_path = self._database()
        self._account_with_dev_token(
            db_path,
            platform="facebook",
            platform_account_id="fb-page-123",
            granted_scopes=["pages_show_list", "pages_read_engagement"],
        )

        def fake_meta(request, timeout):
            return PlatformHttpResponse(
                ok=True,
                status=200,
                json={
                    "data": [
                        {
                            "id": "fb-post-1",
                            "message": "Real Facebook post caption.",
                            "created_time": "2026-06-20T14:00:00+0000",
                            "permalink_url": "https://facebook.com/page/posts/fb-post-1",
                            "full_picture": "https://cdn.example.com/facebook-photo.jpg",
                            "comments": {"summary": {"total_count": 1}},
                            "reactions": {"summary": {"total_count": 2}},
                            "insights": {
                                "data": [
                                    {"name": "post_impressions", "values": [{"value": 100}]},
                                ]
                            },
                        }
                    ]
                },
            )

        with self._env():
            result = MetaAnalyticsService(
                db_path,
                http_client_config=PlatformHttpClientConfig(
                    provider="meta",
                    platform="facebook",
                    safetyMode=NetworkSafetyMode.ENABLED,
                    allowNetwork=True,
                    transport=fake_meta,
                ),
            ).sync(platforms=["facebook", "instagram"], limit=1)

        self.assertEqual(result.createdCount, 1)
        with closing(sqlite3.connect(db_path)) as connection:
            import_platform = connection.execute(
                "SELECT platform FROM analytics_imports WHERE id = ?",
                (result.importId,),
            ).fetchone()[0]
        self.assertIsNone(import_platform)

    def test_missing_real_oauth_flags_prevent_network_call(self):
        db_path = self._database()
        self._account_with_dev_token(
            db_path,
            platform="facebook",
            platform_account_id="fb-page-123",
            granted_scopes=["pages_show_list", "pages_read_engagement"],
        )

        def fail_if_called(request, timeout):
            raise AssertionError("network transport should not be called")

        with patch.dict("os.environ", {"INTEGRATIONS_MODE": "mock"}, clear=False):
            with self.assertRaises(MetaAnalyticsError) as context:
                MetaAnalyticsService(
                    db_path,
                    http_client_config=PlatformHttpClientConfig(
                        provider="meta",
                        platform="facebook",
                        safetyMode=NetworkSafetyMode.ENABLED,
                        allowNetwork=True,
                        transport=fail_if_called,
                    ),
                ).sync(platforms=["facebook"])

        self.assertIn("real_oauth_mode_required", context.exception.error_codes)

    def test_unexpected_sync_error_details_are_redacted(self):
        db_path = self._database()
        self._account_with_dev_token(
            db_path,
            platform="facebook",
            platform_account_id="fb-page-123",
            granted_scopes=["pages_show_list", "pages_read_engagement"],
        )

        with self._env():
            service = MetaAnalyticsService(db_path)
            with patch.object(
                service,
                "_fetch_facebook_posts",
                side_effect=RuntimeError("transport failed with access_token=meta-secret-leak"),
            ):
                result = service.sync(platforms=["facebook"])

        serialized_errors = json.dumps(result.errors)
        self.assertEqual(result.errorCount, 1)
        self.assertIn("[REDACTED", serialized_errors)
        self.assertNotIn("meta-secret-leak", serialized_errors)


if __name__ == "__main__":
    unittest.main()
