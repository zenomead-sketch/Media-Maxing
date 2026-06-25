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

from scripts.connectors.meta.config import load_meta_config
from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.services.analytics import METRIC_FIELDS, calculate_analytics_rates
from scripts.services.platform_http_client import (
    PlatformHttpClient,
    PlatformHttpClientConfig,
    PlatformHttpResponse,
    redact_http_value,
    redact_raw_text,
)
from scripts.services.token_security import is_token_expired


META_ANALYTICS_PLATFORMS = {"facebook", "instagram"}
FACEBOOK_ANALYTICS_REQUIRED_SCOPES = {"pages_show_list", "pages_read_engagement"}
INSTAGRAM_ANALYTICS_REQUIRED_SCOPES = {"instagram_basic", "instagram_manage_insights"}


class MetaAnalyticsError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class MetaAnalyticsSyncResult:
    createdCount: int
    updatedCount: int
    skippedCount: int
    errorCount: int
    importId: str
    platforms: list[str]
    syncedPosts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "createdCount": self.createdCount,
            "updatedCount": self.updatedCount,
            "skippedCount": self.skippedCount,
            "errorCount": self.errorCount,
            "importId": self.importId,
            "platforms": self.platforms,
            "syncedPosts": self.syncedPosts,
            "warnings": self.warnings,
            "errors": self.errors,
            "source": "platform_api",
            "provider": "meta",
        }


class MetaAnalyticsService:
    """Guarded Facebook/Instagram post analytics sync.

    The service reads post/media metrics from Meta only when real OAuth and real
    network flags are enabled. It stores normalized snapshots locally with
    source=platform_api so manual and mock metrics remain visibly distinct.
    """

    def __init__(
        self,
        database_path: str | Path | None = None,
        *,
        http_client_config: PlatformHttpClientConfig | None = None,
    ):
        self.database_path = initialize_database(resolve_database_path(database_path))
        self.http_client_config = http_client_config

    def sync(
        self,
        *,
        platforms: list[str] | None = None,
        brand_profile_id: str | None = None,
        limit: int = 25,
    ) -> MetaAnalyticsSyncResult:
        self._validate_environment()
        selected_platforms = _normalize_platforms(platforms)
        limit = max(1, min(int(limit or 25), 100))
        imported_at = _now_utc()
        import_id = self._record_import(
            platform=selected_platforms[0] if len(selected_platforms) == 1 else None,
            status="pending",
            records_imported=0,
            records_skipped=0,
            error_message=None,
            imported_at=imported_at,
        )

        created = 0
        updated = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[dict[str, Any]] = []
        synced_posts: list[dict[str, Any]] = []
        for account in self._list_accounts(selected_platforms, brand_profile_id):
            platform = account["platform"]
            try:
                self._validate_account(account)
                token = self._require_access_token(account["id"], platform)
                posts = (
                    self._fetch_facebook_posts(account, token, limit)
                    if platform == "facebook"
                    else self._fetch_instagram_media(account, token, limit)
                )
                if not posts:
                    warnings.append(
                        f"{platform}: No recent post analytics returned for {account['display_name']}."
                    )
                for post in posts:
                    published_post_id = self._upsert_published_post(
                        account=account,
                        post=post,
                    )
                    outcome = self._upsert_snapshot(
                        brand_profile_id=account["brand_profile_id"],
                        platform=platform,
                        published_post_id=published_post_id,
                        post=post,
                        imported_at=imported_at,
                    )
                    if outcome == "created":
                        created += 1
                    elif outcome == "updated":
                        updated += 1
                    else:
                        skipped += 1
                    synced_posts.append(
                        {
                            "platform": platform,
                            "publishedPostId": published_post_id,
                            "externalPostId": post["external_id"],
                            "caption": post.get("caption") or "",
                            "permalink": post.get("permalink"),
                            "media": post.get("media", []),
                            "metrics": post.get("metrics", {}),
                        }
                    )
            except MetaAnalyticsError as error:
                errors.append(
                    {
                        "platform": platform,
                        "accountId": account["id"],
                        "message": str(error),
                        "errorCodes": error.error_codes,
                    }
                )
            except Exception as error:
                errors.append(
                    {
                        "platform": platform,
                        "accountId": account["id"],
                        "message": "Meta analytics sync failed safely.",
                        "errorCodes": ["meta_analytics_sync_failed"],
                        "details": redact_raw_text(str(error)),
                    }
                )

        status = "completed" if not errors else "partial" if created or updated else "failed"
        self._update_import(
            import_id,
            status=status,
            records_imported=created + updated,
            records_skipped=skipped,
            error_message="; ".join(error["message"] for error in errors) if errors else None,
        )
        return MetaAnalyticsSyncResult(
            createdCount=created,
            updatedCount=updated,
            skippedCount=skipped,
            errorCount=len(errors),
            importId=import_id,
            platforms=selected_platforms,
            syncedPosts=synced_posts,
            warnings=warnings,
            errors=errors,
        )

    def _validate_environment(self) -> None:
        config = load_meta_config()
        if config.integrationsMode != "real_oauth":
            raise MetaAnalyticsError(
                "Meta analytics sync requires INTEGRATIONS_MODE=real_oauth.",
                ["real_oauth_mode_required"],
            )
        required_truthy = {
            "ENABLE_REAL_OAUTH": os.environ.get("ENABLE_REAL_OAUTH"),
            "ENABLE_REAL_NETWORK_CALLS": os.environ.get("ENABLE_REAL_NETWORK_CALLS"),
            "META_ENABLE_REAL_OAUTH": os.environ.get("META_ENABLE_REAL_OAUTH"),
        }
        missing_flags = [key for key, value in required_truthy.items() if not _truthy(value)]
        if missing_flags:
            raise MetaAnalyticsError(
                "Meta analytics sync is disabled by feature flags.",
                ["meta_analytics_disabled", *missing_flags],
            )
        if not config.clientIdConfigured:
            raise MetaAnalyticsError("META_CLIENT_ID is required.", ["missing_meta_client_id"])
        if not config.graphApiVersion:
            raise MetaAnalyticsError(
                "META_GRAPH_API_VERSION is required.",
                ["missing_meta_graph_version"],
            )

    def _list_accounts(
        self,
        platforms: list[str],
        brand_profile_id: str | None,
    ) -> list[sqlite3.Row]:
        clauses = [
            f"platform IN ({','.join('?' for _ in platforms)})",
            "connection_status IN ('connected', 'limited')",
            "disconnected_at IS NULL",
        ]
        parameters: list[Any] = list(platforms)
        if brand_profile_id:
            clauses.append("(brand_profile_id = ? OR brand_profile_id IS NULL)")
            parameters.append(brand_profile_id)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT *
                FROM social_accounts
                WHERE {" AND ".join(clauses)}
                ORDER BY
                  CASE WHEN brand_profile_id IS NULL THEN 1 ELSE 0 END,
                  platform,
                  last_connected_at DESC,
                  created_at DESC
                """,
                parameters,
            ).fetchall()
        if not rows:
            raise MetaAnalyticsError(
                "No connected Facebook or Instagram accounts are available for analytics sync.",
                ["no_connected_meta_accounts"],
            )
        return rows

    def _validate_account(self, account: sqlite3.Row) -> None:
        if account["requires_reauth"]:
            raise MetaAnalyticsError(
                f"{account['platform']} account requires reauthorization.",
                ["account_requires_reauth"],
            )
        if not _optional_text(account["platform_account_id"]):
            raise MetaAnalyticsError(
                f"{account['platform']} account ID is missing.",
                ["missing_platform_account_id"],
            )
        granted = set(_decode_json(account["granted_scopes_json"], []))
        required = (
            FACEBOOK_ANALYTICS_REQUIRED_SCOPES
            if account["platform"] == "facebook"
            else INSTAGRAM_ANALYTICS_REQUIRED_SCOPES
        )
        missing = sorted(required - granted)
        if missing:
            raise MetaAnalyticsError(
                f"{account['platform']} account is missing analytics scopes: {', '.join(missing)}.",
                ["missing_analytics_scopes", *missing],
            )
        if not _optional_text(account["brand_profile_id"]):
            fallback_brand = self._first_brand_profile_id()
            if fallback_brand is None:
                raise MetaAnalyticsError(
                    "A Brand Brain profile is required before syncing analytics.",
                    ["brand_profile_required"],
                )

    def _require_access_token(self, account_id: str, platform: str) -> str:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT *
                FROM platform_tokens
                WHERE social_account_id = ?
                  AND platform = ?
                  AND revoked_at IS NULL
                ORDER BY
                  CASE token_type WHEN 'page_access' THEN 0 ELSE 1 END,
                  created_at DESC
                LIMIT 1
                """,
                (account_id, platform),
            ).fetchone()
        if row is None:
            raise MetaAnalyticsError(
                f"No {platform} token is available server-side.",
                ["server_token_unavailable"],
            )
        if row["encryption_status"] != "insecure_dev_only":
            raise MetaAnalyticsError(
                "Analytics sync currently requires explicit local development token storage.",
                ["server_token_unavailable"],
            )
        if os.environ.get("APP_ENV") != "development" or not _truthy(
            os.environ.get("ALLOW_INSECURE_TOKEN_STORAGE")
        ):
            raise MetaAnalyticsError(
                "Insecure token retrieval is allowed only in explicit local development mode.",
                ["insecure_token_mode_blocked"],
            )
        if is_token_expired(row["access_token_expires_at"]):
            raise MetaAnalyticsError(f"{platform} token is expired.", ["token_expired"])
        token = _optional_text(row["encrypted_access_token"])
        if not token:
            raise MetaAnalyticsError(
                f"{platform} token value is not available server-side.",
                ["server_token_unavailable"],
            )
        return token

    def _fetch_facebook_posts(
        self,
        account: sqlite3.Row,
        token: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        version = load_meta_config().graphApiVersion
        url = f"https://graph.facebook.com/{version}/{account['platform_account_id']}/posts"
        fields = (
            "id,message,created_time,permalink_url,full_picture,"
            "shares,comments.limit(0).summary(true),reactions.limit(0).summary(true),"
            "attachments{media,type,url,subattachments},"
            "insights.metric(post_impressions,post_impressions_unique,post_engaged_users,post_clicks,post_video_views)"
        )
        response = self._client("facebook").get(
            url,
            query={
                "fields": fields,
                "limit": limit,
                "access_token": token,
            },
        )
        payload = self._require_payload(response, "facebook")
        return [_normalize_facebook_post(item) for item in payload.get("data", []) if isinstance(item, dict)]

    def _fetch_instagram_media(
        self,
        account: sqlite3.Row,
        token: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        version = load_meta_config().graphApiVersion
        url = f"https://graph.facebook.com/{version}/{account['platform_account_id']}/media"
        fields = (
            "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,"
            "like_count,comments_count,children{media_type,media_url,thumbnail_url,permalink},"
            "insights.metric(views,reach,likes,comments,saved,shares,total_interactions)"
        )
        response = self._client("instagram").get(
            url,
            query={
                "fields": fields,
                "limit": limit,
                "access_token": token,
            },
        )
        payload = self._require_payload(response, "instagram")
        return [_normalize_instagram_media(item) for item in payload.get("data", []) if isinstance(item, dict)]

    def _client(self, platform: str) -> PlatformHttpClient:
        if self.http_client_config is not None:
            config = self.http_client_config
        else:
            config = PlatformHttpClientConfig(
                provider="meta",
                platform=platform,
                allowNetwork=True,
            )
        return PlatformHttpClient(config)

    def _require_payload(self, response: PlatformHttpResponse, platform: str) -> dict[str, Any]:
        if not response.ok:
            provider_error = response.error.providerError if response.error else None
            codes = ["meta_analytics_provider_error"]
            if provider_error:
                if provider_error.requiresReauth:
                    codes.append("requires_reauth")
                if provider_error.missingPermission:
                    codes.append("missing_permission")
                if provider_error.rateLimited:
                    codes.append("rate_limited")
            raise MetaAnalyticsError(
                response.error.message if response.error else f"{platform} analytics request failed.",
                codes,
            )
        if not isinstance(response.json, dict):
            raise MetaAnalyticsError(
                f"{platform} analytics response was not JSON.",
                ["invalid_provider_response"],
            )
        return response.json

    def _upsert_published_post(
        self,
        *,
        account: sqlite3.Row,
        post: dict[str, Any],
    ) -> str:
        external_id = post["external_id"]
        now = _now_utc()
        brand_profile_id = account["brand_profile_id"] or self._first_brand_profile_id()
        metadata = {
            "source": "meta_analytics_sync",
            "platformAccountId": account["platform_account_id"],
            "brandProfileId": brand_profile_id,
            "caption": post.get("caption") or "",
            "media": post.get("media", []),
            "accountDisplayName": account["display_name"],
            "realPlatformAnalytics": True,
        }
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                """
                SELECT id
                FROM published_posts
                WHERE platform = ?
                  AND external_post_id = ?
                LIMIT 1
                """,
                (account["platform"], external_id),
            ).fetchone()
            post_id = existing["id"] if existing else f"published-meta-{uuid.uuid4().hex[:12]}"
            if existing:
                connection.execute(
                    """
                    UPDATE published_posts
                    SET permalink = ?,
                        published_at = ?,
                        metadata_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (post.get("permalink"), post["posted_at"], _json(metadata), now, post_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO published_posts (
                      id, scheduled_post_id, generated_post_id, platform,
                      publish_mode, external_post_id, permalink, published_at,
                      metadata_json, created_at, updated_at
                    ) VALUES (?, NULL, NULL, ?, 'platform_api', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post_id,
                        account["platform"],
                        external_id,
                        post.get("permalink"),
                        post["posted_at"],
                        _json(metadata),
                        now,
                        now,
                    ),
                )
            connection.commit()
        return post_id

    def _upsert_snapshot(
        self,
        *,
        brand_profile_id: str | None,
        platform: str | None,
        published_post_id: str,
        post: dict[str, Any],
        imported_at: str,
    ) -> str:
        brand_id = brand_profile_id or self._first_brand_profile_id()
        if not brand_id:
            return "skipped"
        snapshot_date = _today_utc()
        metrics = {
            field: int(post.get("metrics", {}).get(field, 0) or 0)
            for field in METRIC_FIELDS
        }
        rates = calculate_analytics_rates(metrics)
        raw_metrics = {
            "source": "meta_analytics_sync",
            "provider": "meta",
            "realPlatformAnalytics": True,
            "externalPostId": post["external_id"],
            "caption": post.get("caption") or "",
            "postedAt": post["posted_at"],
            "permalink": post.get("permalink"),
            "media": post.get("media", []),
            "providerMetrics": redact_http_value(post.get("provider_metrics", {})).value,
            "syncedAt": imported_at,
        }
        now = _now_utc()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                """
                SELECT id
                FROM analytics_snapshots
                WHERE source = 'platform_api'
                  AND snapshot_date = ?
                  AND published_post_id = ?
                LIMIT 1
                """,
                (snapshot_date, published_post_id),
            ).fetchone()
            if existing:
                connection.execute(
                    f"""
                    UPDATE analytics_snapshots
                    SET {", ".join(f"{field} = ?" for field in METRIC_FIELDS)},
                        engagement_rate = ?,
                        click_through_rate = ?,
                        lead_rate = ?,
                        raw_metrics_json = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        *(metrics[field] for field in METRIC_FIELDS),
                        rates["engagementRate"],
                        rates["clickThroughRate"],
                        rates["leadRate"],
                        _json(raw_metrics),
                        "Synced from Meta Graph API. Metrics remain stored locally.",
                        now,
                        existing["id"],
                    ),
                )
                outcome = "updated"
            else:
                connection.execute(
                    f"""
                    INSERT INTO analytics_snapshots (
                      id, published_post_id, scheduled_post_id, generated_post_id,
                      brand_profile_id, platform, source, snapshot_date,
                      {", ".join(METRIC_FIELDS)},
                      engagement_rate, click_through_rate, lead_rate,
                      raw_metrics_json, notes, created_at, updated_at
                    ) VALUES (
                      ?, ?, NULL, NULL, ?, ?, 'platform_api', ?,
                      {", ".join("?" for _ in METRIC_FIELDS)},
                      ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        str(uuid.uuid4()),
                        published_post_id,
                        brand_id,
                        platform,
                        snapshot_date,
                        *(metrics[field] for field in METRIC_FIELDS),
                        rates["engagementRate"],
                        rates["clickThroughRate"],
                        rates["leadRate"],
                        _json(raw_metrics),
                        "Synced from Meta Graph API. Metrics remain stored locally.",
                        now,
                        now,
                    ),
                )
                outcome = "created"
            connection.commit()
        return outcome

    def _record_import(
        self,
        *,
        platform: str,
        status: str,
        records_imported: int,
        records_skipped: int,
        error_message: str | None,
        imported_at: str,
    ) -> str:
        import_id = f"meta-analytics-import-{uuid.uuid4().hex[:12]}"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                INSERT INTO analytics_imports (
                  id, source, platform, import_type, status,
                  records_imported, records_skipped, error_message,
                  imported_at, created_at
                ) VALUES (?, 'platform_api', ?, 'platform_sync', ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    platform,
                    status,
                    records_imported,
                    records_skipped,
                    error_message,
                    imported_at,
                    imported_at,
                ),
            )
            connection.commit()
        return import_id

    def _update_import(
        self,
        import_id: str,
        *,
        status: str,
        records_imported: int,
        records_skipped: int,
        error_message: str | None,
    ) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                """
                UPDATE analytics_imports
                SET status = ?,
                    records_imported = ?,
                    records_skipped = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (status, records_imported, records_skipped, error_message, import_id),
            )
            connection.commit()

    def _first_brand_profile_id(self) -> str | None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT id FROM brand_profiles ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        return row[0] if row else None


def _normalize_facebook_post(item: dict[str, Any]) -> dict[str, Any]:
    provider_metrics = _insight_map(item.get("insights"))
    reaction_total = _summary_total(item.get("reactions"))
    metrics = {
        "impressions": _metric_number(provider_metrics.get("post_impressions")),
        "reach": _metric_number(provider_metrics.get("post_impressions_unique")),
        "views": _metric_number(provider_metrics.get("post_video_views")),
        "likes": reaction_total,
        "comments": _summary_total(item.get("comments")),
        "shares": _count_value(item.get("shares")),
        "saves": 0,
        "clicks": _metric_number(provider_metrics.get("post_clicks")),
        "profile_visits": 0,
        "follows": 0,
        "leads": 0,
        "messages": 0,
        "calls": 0,
        "website_clicks": 0,
    }
    return {
        "external_id": str(item.get("id") or "").strip(),
        "caption": item.get("message") or "",
        "posted_at": _normalize_provider_time(item.get("created_time")),
        "permalink": item.get("permalink_url"),
        "media": _facebook_media(item),
        "metrics": metrics,
        "provider_metrics": provider_metrics,
    }


def _normalize_instagram_media(item: dict[str, Any]) -> dict[str, Any]:
    provider_metrics = _insight_map(item.get("insights"))
    likes = _metric_number(provider_metrics.get("likes")) or _metric_number(
        item.get("like_count")
    )
    comments = _metric_number(provider_metrics.get("comments")) or _metric_number(
        item.get("comments_count")
    )
    metrics = {
        "impressions": 0,
        "reach": _metric_number(provider_metrics.get("reach")),
        "views": _metric_number(provider_metrics.get("views")),
        "likes": likes,
        "comments": comments,
        "shares": _metric_number(provider_metrics.get("shares")),
        "saves": _metric_number(provider_metrics.get("saved")),
        "clicks": 0,
        "profile_visits": 0,
        "follows": 0,
        "leads": 0,
        "messages": 0,
        "calls": 0,
        "website_clicks": 0,
    }
    return {
        "external_id": str(item.get("id") or "").strip(),
        "caption": item.get("caption") or "",
        "posted_at": _normalize_provider_time(item.get("timestamp")),
        "permalink": item.get("permalink"),
        "media": _instagram_media(item),
        "metrics": metrics,
        "provider_metrics": provider_metrics,
    }


def _insight_map(raw_insights: Any) -> dict[str, Any]:
    data = raw_insights.get("data", []) if isinstance(raw_insights, dict) else []
    metrics: dict[str, Any] = {}
    for item in data:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        values = item.get("values") if isinstance(item.get("values"), list) else []
        value = values[-1].get("value") if values and isinstance(values[-1], dict) else 0
        metrics[str(item["name"])] = value
    return metrics


def _facebook_media(item: dict[str, Any]) -> list[dict[str, str]]:
    media: list[dict[str, str]] = []
    if item.get("full_picture"):
        media.append({"type": "image", "url": str(item["full_picture"])})
    attachments = item.get("attachments", {}).get("data", []) if isinstance(item.get("attachments"), dict) else []
    for attachment in attachments:
        _add_facebook_attachment_media(media, attachment)
        subattachments = (
            attachment.get("subattachments", {}).get("data", [])
            if isinstance(attachment, dict) and isinstance(attachment.get("subattachments"), dict)
            else []
        )
        for subattachment in subattachments:
            _add_facebook_attachment_media(media, subattachment)
    return _unique_media(media)


def _add_facebook_attachment_media(media: list[dict[str, str]], attachment: Any) -> None:
    if not isinstance(attachment, dict):
        return
    image = attachment.get("media", {}).get("image") if isinstance(attachment.get("media"), dict) else None
    if isinstance(image, dict) and image.get("src"):
        media.append({"type": "image", "url": str(image["src"])})
    elif attachment.get("url"):
        media.append({"type": str(attachment.get("type") or "link"), "url": str(attachment["url"])})


def _instagram_media(item: dict[str, Any]) -> list[dict[str, str]]:
    media: list[dict[str, str]] = []
    url = item.get("media_url") or item.get("thumbnail_url")
    if url:
        media.append({"type": _media_type(item.get("media_type")), "url": str(url)})
    children = item.get("children", {}).get("data", []) if isinstance(item.get("children"), dict) else []
    for child in children:
        child_url = child.get("media_url") or child.get("thumbnail_url") if isinstance(child, dict) else None
        if child_url:
            media.append({"type": _media_type(child.get("media_type")), "url": str(child_url)})
    return _unique_media(media)


def _unique_media(media: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in media:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)
    return unique


def _media_type(value: Any) -> str:
    normalized = str(value or "").lower()
    if "video" in normalized or "reel" in normalized:
        return "video"
    if "carousel" in normalized:
        return "carousel"
    return "image"


def _summary_total(value: Any) -> int:
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, dict):
            return _metric_number(summary.get("total_count"))
    return 0


def _count_value(value: Any) -> int:
    if isinstance(value, dict):
        return _metric_number(value.get("count"))
    return _metric_number(value)


def _metric_number(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_metric_number(child) for child in value.values())
    if isinstance(value, bool) or value is None:
        return 0
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _normalize_platforms(platforms: list[str] | None) -> list[str]:
    selected = [
        str(platform).strip().lower()
        for platform in (platforms or ["facebook", "instagram"])
        if str(platform).strip()
    ]
    invalid = sorted(set(selected) - META_ANALYTICS_PLATFORMS)
    if invalid:
        raise MetaAnalyticsError(
            f"Meta analytics supports only Facebook and Instagram: {', '.join(invalid)}.",
            ["unsupported_meta_analytics_platform"],
        )
    return selected or ["facebook", "instagram"]


def _normalize_provider_time(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return _now_utc()
    try:
        parsed = datetime.fromisoformat(raw.removesuffix("Z") + "+00:00" if raw.endswith("Z") else raw)
    except ValueError:
        return _now_utc()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat() + "T00:00:00Z"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(redact_http_value(value).value, sort_keys=True, separators=(",", ":"))


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in {"1", "true", "yes", "on"})


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
