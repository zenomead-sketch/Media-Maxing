"""Local AI runtime provider.

This adapter targets Ollama's local HTTP API by default. It is intentionally
off unless the user explicitly selects the local provider and enables
``ENABLE_LOCAL_AI_CALLS=true`` in their local environment.

The adapter builds the app's structured ``GeneratedContentBundle`` locally and
uses the local model only for caption/hook text. That keeps validation, safety
review, platform limits, approval defaults, and persistence under the app's
control instead of trusting arbitrary free-form model output.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from scripts.ai.platform_limits import caption_limit_for, trim_to_limit
from scripts.ai.providers.base import AIProvider, AIProviderError, ProviderDisabledError
from scripts.ai.schemas import (
    AIStructuredGenerationRequest,
    AIStructuredGenerationResponse,
    AITextGenerationRequest,
    AITextGenerationResponse,
    CaptionVariant,
    ContentGenerationInput,
    ContentGenerationOptions,
    GeneratedContentBundle,
    GeneratedPostSafetyReview,
    PlatformPostDraft,
)

DEFAULT_LOCAL_AI_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_LOCAL_AI_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT_SECONDS = 60
LOCAL_PROVIDER_PROMPT_VERSION = "ollama-local-v1"


def _env_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _clean_base_url(raw_url: str) -> str:
    cleaned = (raw_url or DEFAULT_LOCAL_AI_BASE_URL).strip().rstrip("/")
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderDisabledError("Local AI runtime URL must be a valid http(s) URL.")
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} and not _env_truthy(
        os.environ.get("ALLOW_NON_LOOPBACK_LOCAL_AI")
    ):
        raise ProviderDisabledError(
            "Local AI runtime must use localhost/127.0.0.1 by default. "
            "Set ALLOW_NON_LOOPBACK_LOCAL_AI=true only for a trusted self-hosted runtime."
        )
    return cleaned


def _clip(text: str, limit: int) -> str:
    return trim_to_limit(" ".join(str(text or "").split()), limit)


def _service_phrase(services: list[str]) -> str:
    return ", ".join(services[:3]) if services else "the listed services"


def _media_summary(media_assets: list[dict[str, Any]]) -> str:
    if not media_assets:
        return "No selected media."
    parts: list[str] = []
    for asset in media_assets[:8]:
        title = asset.get("title") or asset.get("originalFilename") or asset.get("id") or "media"
        angle = asset.get("contentAngle") or asset.get("content_angle") or "unspecified angle"
        service = asset.get("serviceType") or asset.get("service_type") or ""
        parts.append(f"{title} ({angle}{', ' + service if service else ''})")
    return "; ".join(parts)


def _media_ids(media_assets: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for asset in media_assets:
        media_id = asset.get("id") if isinstance(asset, dict) else None
        if isinstance(media_id, str) and media_id.strip():
            ids.append(media_id.strip())
    return ids


def _hashtags(business_name: str, services: list[str], angle: str, count: int) -> list[str]:
    if count <= 0:
        return []
    candidates = [
        "#" + "".join(ch for ch in business_name.title() if ch.isalnum()),
        "#" + "".join(part.title() for part in angle.replace("_", " ").split()),
        "#LocalBusiness",
        "#LocalServiceBusiness",
    ]
    for service in services:
        tag = "#" + "".join(part.title() for part in service.split() if part)
        if len(tag) > 1:
            candidates.append(tag)
    out: list[str] = []
    for tag in candidates:
        if tag and tag != "#" and tag not in out:
            out.append(tag)
    return out[:count]


class LocalProvider(AIProvider):
    name = "local"
    label = "Local AI runtime (Ollama-compatible)"
    requires_network = False

    def __init__(self) -> None:
        self._config_error: str | None = None
        try:
            self.base_url = _clean_base_url(os.environ.get("LOCAL_AI_BASE_URL", ""))
        except ProviderDisabledError as error:
            self.base_url = (os.environ.get("LOCAL_AI_BASE_URL") or DEFAULT_LOCAL_AI_BASE_URL).strip()
            self._config_error = str(error)
        self.model = (os.environ.get("LOCAL_AI_MODEL") or DEFAULT_LOCAL_AI_MODEL).strip()
        self.timeout_seconds = int(
            (os.environ.get("LOCAL_AI_TIMEOUT_SECONDS") or str(DEFAULT_TIMEOUT_SECONDS)).strip()
        )
        self._enabled = _env_truthy(os.environ.get("ENABLE_LOCAL_AI_CALLS"))
        self._allow_network_in_tests = _env_truthy(os.environ.get("ALLOW_NETWORK_IN_TESTS"))
        self._app_env = (os.environ.get("APP_ENV") or "development").strip().lower()

    def _disabled_reason(self) -> str | None:
        if self._config_error:
            return self._config_error
        if not self._enabled:
            return "ENABLE_LOCAL_AI_CALLS=false keeps the local AI runtime disabled."
        if not self.model:
            return "LOCAL_AI_MODEL is empty."
        if self._app_env == "test" and not self._allow_network_in_tests:
            return "APP_ENV=test blocks local AI calls unless ALLOW_NETWORK_IN_TESTS=true."
        return None

    def _ensure_enabled(self) -> None:
        reason = self._disabled_reason()
        if reason:
            raise ProviderDisabledError(f"{self.label} is disabled: {reason}")

    def availability(self) -> dict[str, Any]:
        reason = self._disabled_reason()
        return {
            "id": self.name,
            "label": self.label,
            "requiresNetwork": False,
            "available": reason is None,
            "reason": reason,
        }

    def _ollama_generate(self, prompt: str, *, temperature: float = 0.4) -> str:
        self._ensure_enabled()
        endpoint = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as error:
            raise AIProviderError(
                "Local AI runtime could not be reached. Start Ollama and confirm "
                f"LOCAL_AI_BASE_URL={self.base_url}."
            ) from error
        except TimeoutError as error:
            raise AIProviderError("Local AI runtime timed out while generating.") from error

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as error:
            raise AIProviderError("Local AI runtime returned invalid JSON.") from error
        text = decoded.get("response")
        if not isinstance(text, str) or not text.strip():
            raise AIProviderError("Local AI runtime returned an empty response.")
        return text.strip()

    def generate_text(self, request: AITextGenerationRequest) -> AITextGenerationResponse:
        request.validate()
        text = self._ollama_generate(
            request.prompt,
            temperature=float(request.temperature if request.temperature is not None else 0.4),
        )
        return AITextGenerationResponse(
            text=text,
            provider=self.name,
            model=self.model,
            finish_reason="stop",
            usage={"prompt_chars": len(request.prompt), "completion_chars": len(text)},
            metadata={"local_runtime": "ollama", "base_url": self.base_url},
            is_mock=False,
        )

    def generate_structured(
        self,
        request: AIStructuredGenerationRequest,
    ) -> AIStructuredGenerationResponse:
        request.validate()
        prompt = (
            f"{request.prompt}\n\nReturn only valid JSON for schema {request.schema_name}. "
            "Do not include markdown fences."
        )
        text = self._ollama_generate(prompt, temperature=0.2)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"rawText": text}
        if not isinstance(data, dict):
            data = {"rawValue": data}
        return AIStructuredGenerationResponse(
            data=data,
            schema_name=request.schema_name,
            provider=self.name,
            model=self.model,
            finish_reason="stop",
            usage={"prompt_chars": len(prompt), "completion_chars": len(text)},
            metadata={"local_runtime": "ollama", "base_url": self.base_url},
            is_mock=False,
        )

    def generate_bundle(
        self,
        input: ContentGenerationInput,
        options: ContentGenerationOptions,
    ) -> GeneratedContentBundle:
        input.validate()
        options.validate()
        brand = input.brand_profile
        business_name = str(brand.get("businessName") or "the business").strip()
        voice = str(brand.get("voice") or brand.get("brandVoice") or "helpful and honest").strip()
        services = [
            service.strip()
            for service in (brand.get("services") or [])
            if isinstance(service, str) and service.strip()
        ]
        audience = str(input.target_audience or brand.get("targetAudience") or "local customers")
        media_ids = _media_ids(input.selected_media_assets)
        posts: list[PlatformPostDraft] = []

        for index, platform in enumerate(input.selected_platforms):
            limit = caption_limit_for(platform)
            if options.max_caption_length:
                limit = min(limit, int(options.max_caption_length))
            prompt = self._caption_prompt(
                platform=platform,
                business_name=business_name,
                voice=voice,
                services=services,
                audience=audience,
                input=input,
                options=options,
                character_limit=limit,
            )
            generated = _clip(self._ollama_generate(prompt, temperature=0.35), limit)
            hashtags = _hashtags(
                business_name,
                services,
                input.content_angle,
                options.hashtag_count if options.include_hashtags else 0,
            )
            call_to_action = (
                "Message or call to ask about availability." if options.include_cta else None
            )
            posts.append(
                PlatformPostDraft(
                    platform=platform,
                    headline=f"{business_name}: {input.content_angle.replace('_', ' ').title()}",
                    hook=_clip(generated.split(".")[0] if "." in generated else generated, 120),
                    caption=generated,
                    short_caption=_clip(generated, 110),
                    long_caption=generated,
                    call_to_action=call_to_action,
                    hashtags=hashtags,
                    media_asset_ids=list(media_ids),
                    caption_variants=[
                        CaptionVariant(
                            text=_clip(
                                self._ollama_generate(
                                    prompt + "\n\nWrite one shorter alternate caption.",
                                    temperature=0.4,
                                ),
                                limit,
                            ),
                            style="local_alt",
                        )
                        for _ in range(options.number_of_variants)
                    ],
                    content_goal=input.content_goal,
                    content_angle=input.content_angle,
                    target_audience=audience,
                    suggested_post_time=self._suggested_post_time(platform, index),
                    alt_text=(
                        f"Selected local media for {input.content_angle.replace('_', ' ')}."
                        if media_ids
                        else None
                    ),
                    notes="Generated with local Ollama-compatible runtime. Review before saving.",
                    status="needs_review",
                )
            )

        return GeneratedContentBundle(
            brand_profile_id=input.brand_profile_id(),
            posts=posts,
            prompt_id=options.prompt_id,
            prompt_version=LOCAL_PROVIDER_PROMPT_VERSION,
            generation_provider=self.name,
            prompt_metadata={
                "prompt_id": options.prompt_id,
                "prompt_version": LOCAL_PROVIDER_PROMPT_VERSION,
                "content_goal": input.content_goal,
                "content_angle": input.content_angle,
                "selected_platforms": list(input.selected_platforms),
                "local_ai_runtime": "ollama",
            },
            provider_metadata={
                "provider_label": self.label,
                "model": self.model,
                "base_url": self.base_url,
                "local_only": True,
            },
            safety_review=GeneratedPostSafetyReview(
                flags=[],
                blocking_flags=[],
                reviewer="local_rules",
                notes="Local provider output still receives app safety review after generation.",
            ),
            content_idea_id=input.content_idea_id,
        )

    def _caption_prompt(
        self,
        *,
        platform: str,
        business_name: str,
        voice: str,
        services: list[str],
        audience: str,
        input: ContentGenerationInput,
        options: ContentGenerationOptions,
        character_limit: int,
    ) -> str:
        supported_claims = "; ".join(
            claim for claim in (input.brand_profile.get("supportedClaims") or []) if isinstance(claim, str)
        )
        return "\n".join(
            [
                "Write one social media caption for a local service business.",
                f"Business: {business_name}",
                f"Platform: {platform}",
                f"Voice: {voice}",
                f"Services: {_service_phrase(services)}",
                f"Audience: {audience}",
                f"Content goal: {input.content_goal}",
                f"Content angle: {input.content_angle}",
                f"Selected media context: {_media_summary(input.selected_media_assets)}",
                f"Supported claims only: {supported_claims or 'none listed'}",
                f"User instructions: {input.user_instructions or 'none'}",
                f"Tone: {options.tone or 'helpful'}",
                f"Maximum characters: {character_limit}",
                "Safety rules: do not invent testimonials, pricing, guarantees, availability, licenses, awards, or customer names.",
                "Do not say the post was published. Do not include markdown. Return caption text only.",
            ]
        )

    def _suggested_post_time(self, platform: str, index: int) -> str:
        hour_by_platform = {
            "instagram": 16,
            "facebook": 13,
            "threads": 18,
            "tiktok": 19,
            "youtube": 11,
            "linkedin": 9,
            "x": 8,
        }
        anchor = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        scheduled = (anchor + timedelta(days=index + 1)).replace(
            hour=hour_by_platform.get(platform, 12),
            minute=0,
            second=0,
            microsecond=0,
        )
        return scheduled.strftime("%Y-%m-%dT%H:%M:%S.000Z")
