from __future__ import annotations

from typing import Any

from scripts.connectors.meta.config import load_meta_config
from scripts.connectors.meta.base import MetaConnector
from scripts.connectors.types import (
    ConnectorActionResult,
    ConnectorCapabilities,
    PlatformFeatureStatus,
    PlatformPermissionScope,
)
from scripts.services.platform_http_client import (
    PlatformHttpClient,
    PlatformHttpClientConfig,
    PlatformHttpFilePart,
    PlatformHttpMethod,
    PlatformHttpRequest,
    normalize_provider_error,
    redact_http_value,
)


GUARDED_FACEBOOK_PUBLISH_CONTEXT = "facebook_publishing_service_v1"


class FacebookConnector(MetaConnector):
    def __init__(self) -> None:
        super().__init__(
            platform="facebook",
            label="Facebook",
            capabilities=ConnectorCapabilities(
                canConnect=True,
                canReadProfile=True,
                canPublishText=False,
                canPublishImage=False,
                canReadComments=False,
                canReplyToComments=False,
                canReadAnalytics=False,
                requiresBusinessAccount=False,
                requiresAppReview=True,
                supportsOAuth=True,
                supportsManualExportFallback=True,
            ),
            required_scopes=(
                PlatformPermissionScope(
                    id="pages_show_list",
                    label="Pages list",
                    description="Placeholder scope for listing Facebook Pages the user can manage.",
                    status=PlatformFeatureStatus.SCAFFOLDED,
                ),
                PlatformPermissionScope(
                    id="pages_manage_metadata",
                    label="Page metadata",
                    description="Required for discovering manageable Facebook Page metadata during real OAuth testing.",
                    status=PlatformFeatureStatus.REQUIRES_APP_REVIEW,
                ),
                PlatformPermissionScope(
                    id="pages_read_engagement",
                    label="Page engagement read",
                    description="Placeholder scope for future safe page profile and engagement checks.",
                    status=PlatformFeatureStatus.PLANNED,
                ),
                PlatformPermissionScope(
                    id="pages_manage_posts",
                    label="Page posts manage",
                    description="Required for future real Facebook Page publishing. Use only with explicit approval gates.",
                    required=False,
                    status=PlatformFeatureStatus.REQUIRES_APP_REVIEW,
                ),
            ),
            setup_instructions=(
                "Create or use a Meta developer app and configure Facebook Login for a local callback URL.",
                "Set META_CLIENT_ID, META_CLIENT_SECRET, META_REDIRECT_URI, and optionally META_GRAPH_API_VERSION in the local environment.",
                "Required redirect URI should match the server callback, for example http://localhost:8000/api/connect/facebook/callback.",
                "Connection scopes: pages_show_list, pages_manage_metadata, and pages_read_engagement. Guarded real Page posting also needs pages_manage_posts and explicit local confirmation.",
                "Required account type: Facebook Page access for the business.",
                "App review warning: Meta may require app review before live Page permissions work.",
                "Local development note: mock OAuth works without credentials; real network calls are disabled by default.",
                "Safety note: Publishing is disabled by default; the guarded Facebook service can publish one text or single-image Page post only when every safety gate passes.",
            ),
        )

    def publishText(
        self,
        payload: dict[str, Any] | None = None,
        *,
        http_client_config: PlatformHttpClientConfig | None = None,
    ) -> ConnectorActionResult:
        payload = payload or {}
        page_id = _optional_payload_text(payload, "pageId")
        message = _optional_payload_text(payload, "message")
        page_token = _optional_payload_text(payload, "pageAccessToken")
        guarded_context = _optional_payload_text(payload, "guardedServiceContext")
        if guarded_context != GUARDED_FACEBOOK_PUBLISH_CONTEXT:
            return ConnectorActionResult(
                success=False,
                status="disabled_by_policy",
                message=(
                    "Direct Facebook text publishing is disabled by policy. Use the guarded "
                    "FacebookPublishingService so confirmation, preflight, emergency pause, "
                    "and token checks run first."
                ),
                metadata={
                    "platform": "facebook",
                    "realPublishingEnabled": False,
                    "reason": "missing_guarded_service_context",
                },
            )
        if not page_id or not message or not page_token:
            return ConnectorActionResult(
                success=False,
                status="disabled_by_policy",
                message=(
                    "Direct Facebook text publishing is disabled by policy. It is only available through the guarded "
                    "FacebookPublishingService with explicit user confirmation, a ready "
                    "queue item, and server-side token handling."
                ),
                metadata={
                    "platform": "facebook",
                    "realPublishingEnabled": False,
                    "reason": "use_guarded_facebook_publishing_service",
                },
            )
        config = load_meta_config()
        request = PlatformHttpRequest(
            method=PlatformHttpMethod.POST,
            url=f"https://graph.facebook.com/{config.graphApiVersion}/{page_id}/feed",
            headers={"Authorization": f"Bearer {page_token}"},
            formBody={"message": message},
        )
        response = PlatformHttpClient(
            http_client_config
            or PlatformHttpClientConfig(
                provider="meta",
                platform="facebook",
                allowNetwork=True,
            )
        ).request(request)
        if not response.ok:
            provider_error = (
                response.error.providerError
                if response.error and response.error.providerError
                else normalize_provider_error(
                    provider="meta",
                    platform="facebook",
                    status=response.status,
                    payload=response.json,
                    raw_text=response.text,
                )
            )
            return ConnectorActionResult(
                success=False,
                status="provider_error",
                message=provider_error.userSafeMessage,
                metadata={
                    "platform": "facebook",
                    "providerStatus": provider_error.status,
                    "errorCode": provider_error.code,
                    "requiresReauth": provider_error.requiresReauth,
                    "rateLimited": provider_error.rateLimited,
                    "rawRedacted": provider_error.rawRedacted,
                    "realPublishingEnabled": True,
                },
            )
        body = response.json if isinstance(response.json, dict) else {}
        external_id = _optional_payload_text(body, "id")
        permalink = _optional_payload_text(body, "permalink_url", "permalink")
        return ConnectorActionResult(
            success=True,
            status="published",
            message="Facebook Page text post was published through the guarded connector.",
            metadata={
                "platform": "facebook",
                "externalPostId": external_id,
                "permalink": permalink,
                "providerResponse": redact_http_value(body).value,
                "realPublishingEnabled": True,
            },
        )

    def publishImage(
        self,
        payload: dict[str, Any] | None = None,
        *,
        http_client_config: PlatformHttpClientConfig | None = None,
    ) -> ConnectorActionResult:
        payload = payload or {}
        page_id = _optional_payload_text(payload, "pageId")
        message = _optional_payload_text(payload, "message") or ""
        page_token = _optional_payload_text(payload, "pageAccessToken")
        filename = _optional_payload_text(payload, "filename") or "facebook-photo.jpg"
        content_type = _optional_payload_text(payload, "contentType") or "image/jpeg"
        image_bytes = payload.get("imageBytes")
        guarded_context = _optional_payload_text(payload, "guardedServiceContext")
        if guarded_context != GUARDED_FACEBOOK_PUBLISH_CONTEXT:
            return ConnectorActionResult(
                success=False,
                status="disabled_by_policy",
                message=(
                    "Direct Facebook image publishing is disabled by policy. Use the guarded "
                    "FacebookPublishingService so confirmation, preflight, emergency pause, "
                    "and token/media checks run first."
                ),
                metadata={
                    "platform": "facebook",
                    "realPublishingEnabled": False,
                    "reason": "missing_guarded_service_context",
                },
            )
        if not page_id or not page_token or not isinstance(image_bytes, bytes) or not image_bytes:
            return ConnectorActionResult(
                success=False,
                status="disabled_by_policy",
                message=(
                    "Direct Facebook image publishing is disabled by policy. It is only available through the "
                    "guarded FacebookPublishingService with explicit user confirmation, a ready queue item, "
                    "and server-side local media handling."
                ),
                metadata={
                    "platform": "facebook",
                    "realPublishingEnabled": False,
                    "reason": "use_guarded_facebook_publishing_service",
                },
            )
        config = load_meta_config()
        request = PlatformHttpRequest(
            method=PlatformHttpMethod.POST,
            url=f"https://graph.facebook.com/{config.graphApiVersion}/{page_id}/photos",
            headers={"Authorization": f"Bearer {page_token}"},
            multipartFields={
                "message": message,
                "published": "true",
            },
            multipartFiles=(
                PlatformHttpFilePart(
                    fieldName="source",
                    filename=filename,
                    contentType=content_type,
                    content=image_bytes,
                ),
            ),
        )
        response = PlatformHttpClient(
            http_client_config
            or PlatformHttpClientConfig(
                provider="meta",
                platform="facebook",
                allowNetwork=True,
            )
        ).request(request)
        if not response.ok:
            provider_error = (
                response.error.providerError
                if response.error and response.error.providerError
                else normalize_provider_error(
                    provider="meta",
                    platform="facebook",
                    status=response.status,
                    payload=response.json,
                    raw_text=response.text,
                )
            )
            return ConnectorActionResult(
                success=False,
                status="provider_error",
                message=provider_error.userSafeMessage,
                metadata={
                    "platform": "facebook",
                    "providerStatus": provider_error.status,
                    "errorCode": provider_error.code,
                    "requiresReauth": provider_error.requiresReauth,
                    "rateLimited": provider_error.rateLimited,
                    "rawRedacted": provider_error.rawRedacted,
                    "realPublishingEnabled": True,
                },
            )
        body = response.json if isinstance(response.json, dict) else {}
        external_photo_id = _optional_payload_text(body, "id")
        external_post_id = _optional_payload_text(body, "post_id") or external_photo_id
        permalink = _optional_payload_text(body, "permalink_url", "permalink")
        return ConnectorActionResult(
            success=True,
            status="published",
            message="Facebook Page photo post was published through the guarded connector.",
            metadata={
                "platform": "facebook",
                "externalPhotoId": external_photo_id,
                "externalPostId": external_post_id,
                "permalink": permalink,
                "providerResponse": redact_http_value(body).value,
                "realPublishingEnabled": True,
                "publishKind": "facebook_photo",
            },
        )


def _required_payload_text(source: dict[str, Any], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required for Facebook publishing.")
    return value.strip()


def _optional_payload_text(source: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
