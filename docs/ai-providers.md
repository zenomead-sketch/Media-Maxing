# AI Providers

This document describes the AI provider abstraction. Mock provider is the
default safe path. The local provider can call an Ollama-compatible runtime on
the same machine when explicitly enabled. Cloud providers remain scaffolded and
disabled until they are implemented behind their own safety gates.

## Goals

- One stable interface for every AI provider.
- Mock provider is the default for development and tests.
- Providers fail safely if any safety gate is off or any required
  configuration is missing.
- No SDK is imported at module load time, so missing optional packages
  cannot break tests.
- Provider output is structured. Free-form text is not accepted as
  production data downstream.

## Files

- `scripts/ai/__init__.py`
- `scripts/ai/schemas.py` — dataclasses for inputs and outputs.
- `scripts/ai/providers/__init__.py`
- `scripts/ai/providers/base.py` — `AIProvider` ABC and
  `RealProviderStub` shared scaffolding plus the disabled-error types.
- `scripts/ai/providers/mock.py` — `MockProvider`, deterministic.
- `scripts/ai/providers/openai.py` — OpenAI stub.
- `scripts/ai/providers/anthropic.py` — Anthropic stub.
- `scripts/ai/providers/local.py` — Local Ollama-compatible runtime adapter.
- `scripts/ai/providers/registry.py` — `get_provider`,
  `list_available_providers`.

## Provider Interface

Every provider implements three operations:

```python
class AIProvider(ABC):
    name: str
    label: str
    requires_network: bool

    def generate_text(self, request: AITextGenerationRequest) -> AITextGenerationResponse: ...
    def generate_structured(self, request: AIStructuredGenerationRequest) -> AIStructuredGenerationResponse: ...
    def generate_bundle(self, input, options) -> GeneratedContentBundle: ...
    def availability(self) -> dict: ...
```

- `generate_text` returns a free-form text response.
- `generate_structured` returns a dict response under a named schema
  (for example `"platform_post_draft"`, `"hashtag_set"`,
  `"safety_review"`).
- `generate_bundle` is the higher-level operation used by the content
  generation service. It accepts `ContentGenerationInput` plus
  `ContentGenerationOptions` and returns a `GeneratedContentBundle`
  with one `PlatformPostDraft` per requested platform, prompt metadata,
  provider metadata, and a `GeneratedPostSafetyReview`.

## Errors

- `AIProviderError` — base class. Catch this when you want one
  fallback path for every provider failure.
- `ProviderDisabledError` — raised when a safety gate or required
  configuration is missing, or when a real adapter is not yet
  implemented.
- `ProviderConfigurationError` — raised on unknown provider names.

## Schemas

`scripts/ai/schemas.py` defines:

- `AIProviderName` (`Literal["mock", "openai", "anthropic", "local"]`)
- `AITextGenerationRequest` / `AITextGenerationResponse`
- `AIStructuredGenerationRequest` / `AIStructuredGenerationResponse`
- `ContentGenerationInput`
  (`brand_profile`, `selected_media_assets`, `selected_platforms`,
  `content_goal`, `content_angle`, `campaign_name`, `target_audience`,
  `location_context`, `offer_context`, `user_instructions`,
  `approval_required`, `content_idea_id`)
- `ContentGenerationOptions`
  (`provider_name`, `prompt_id`, `number_of_variants`,
  `include_hashtags`, `include_emojis`, `include_cta`, `tone`,
  `creativity_level`, `max_caption_length`, `require_safety_review`,
  `generate_platform_specific_versions`, `hashtag_count`)
- `PlatformPostDraft`
  (`platform`, `caption`, `headline`, `short_caption`, `long_caption`,
  `hook`, `call_to_action`, `hashtags`, `media_asset_ids`,
  `content_angle`, `content_goal`, `target_audience`,
  `suggested_post_time`, `alt_text`, `notes`, `caption_variants`,
  `safety_flags`, `score`, `status`)
- `CaptionVariant`, `HashtagSet`
- `GeneratedPostScore` (0–100 with optional breakdown)
- `DraftImprovementSuggestion`
  (`suggestion_text`, `target_field`, `severity`, `notes`)
- `StrategyIdea`, `ContentStrategyBrief`
- `GeneratedPostSafetyReview`
  (`flags`, `blocking_flags ⊆ flags`, `reviewer ∈ {local_rules, ai, manual}`,
  `notes`, `suggested_fixes`)
- `GeneratedContentBundle`
  (`brand_profile_id`, `posts`, `prompt_id`, `prompt_version`,
  `generation_provider`, `prompt_metadata`, `provider_metadata`,
  `safety_review`, `strategy_brief`, `caption_variants`,
  `hashtag_sets`, `improvement_suggestions`, `content_idea_id`,
  `created_at`)

Enum constants exported for cross-checking: `SUPPORTED_PLATFORMS`,
`SUPPORTED_GOALS`, `SUPPORTED_ANGLES`, `SUPPORTED_PROVIDERS`,
`APPROVAL_STATUSES`, `CREATIVITY_LEVELS`, `SUGGESTION_SEVERITIES`,
`SAFETY_REVIEWERS`, `SAFETY_FLAG_VOCABULARY` (the 10 safety categories
documented in AGENTS.md).

Validation is enforced in `__post_init__` and a `validate()` method on
the input types. Enums for platform, goal, angle, and provider are
checked against the lists in this module.

These shapes match the TypeScript types in
`packages/types/index.ts` where they overlap. Adding a field requires
updating both files in lockstep.

## Mock Provider

`MockProvider` is deterministic by design:

- No randomness, no clock reads, no network access.
- Caption is templated from the brand profile (`businessName`, `voice`,
  `services`, `supportedClaims`, `targetAudience`), the chosen goal, the
  chosen angle, and the requested platforms.
- Hashtags are derived from the business name and services in a
  stable order.
- `prompt_id` defaults to `platform_post_generator_v1`.
- `prompt_version` is `"v1"`.
- `generation_provider` is `"mock"`.
- `provider_metadata` includes `deterministic: True`, `mock: True`, and
  an `input_fingerprint` so identical inputs can be recognised in tests.
- `safety_review` is returned empty by the mock provider. A separate
  safety review module added later (Batch 3 Step 3) is responsible for
  flagging unsupported claims, invented testimonials, and similar
  issues. The mock provider's notes field makes this explicit.

The mock provider raises `SchemaValidationError` for invalid inputs and
never raises `ProviderDisabledError`.

## Local Ollama Provider

`LocalProvider` uses Ollama's local `/api/generate` endpoint by default. It is
designed for fully local generation on the user's machine, with the app still
owning structure, validation, safety review, approval status, and persistence.

The local provider is disabled unless all of these are true:

- Settings or `.env` select `local` as the AI provider.
- `ENABLE_LOCAL_AI_CALLS=true`.
- `LOCAL_AI_BASE_URL` points to `localhost`, `127.0.0.1`, or `::1` by default.
- `LOCAL_AI_MODEL` names a model already pulled into Ollama.
- Tests still block live network unless `ALLOW_NETWORK_IN_TESTS=true`.

Recommended local `.env` values:

```text
AI_PROVIDER_PREFERENCE=local
ENABLE_LOCAL_AI_CALLS=true
LOCAL_AI_BASE_URL=http://127.0.0.1:11434
LOCAL_AI_MODEL=llama3.1:8b
LOCAL_AI_TIMEOUT_SECONDS=60
```

The user must install Ollama separately and pull the selected model before
using this mode. Example:

```text
ollama pull llama3.1:8b
```

The adapter sends only the generation prompt to the local runtime. It does not
publish posts, schedule posts, send replies, or call social platforms.

## Cloud Provider Stubs

`OpenAIProvider` and `AnthropicProvider` remain scaffolds. They share
`RealProviderStub`, which reads these gates:

1. `INTEGRATIONS_MODE` must be a non-mock value.
2. `ENABLE_REAL_NETWORK_CALLS` must be truthy
   (`true`, `1`, `yes`, or `on`).
3. The provider's required key must be present and non-empty:
   - OpenAI: `OPENAI_API_KEY`
   - Anthropic: `ANTHROPIC_API_KEY`

If any gate fails, `generate_bundle` raises `ProviderDisabledError` with the
reason. If every gate passes, these cloud providers still raise
`ProviderDisabledError` with a "not yet implemented" message. This keeps
external AI costs and data-sharing off until a future explicit cloud-provider
task implements them safely.

Constructors never raise. This lets the Settings UI safely list every provider
with a reason explaining why it is currently unavailable.

## Registry

```python
from scripts.ai.providers.registry import (
    get_provider,
    list_available_providers,
    provider_from_config,
)

provider = get_provider()                       # defaults to mock
provider = get_provider("openai")               # raises ProviderDisabledError on use
status = list_available_providers()             # safe DTO list for the Settings UI
provider = provider_from_config(config)         # resolve from AIProviderConfig
```

`get_provider` is case- and whitespace-insensitive. Unknown names raise
`ProviderConfigurationError`.

## Configuration

`scripts/ai/config.py` defines :class:`AIProviderConfig`. It is the
single source of truth for "which provider should the app use right
now". It reads from the environment and accepts an optional
``provider_preference`` argument so callers that have already loaded
app settings can pass ``settings.aiProviderPreference`` directly.

```python
from scripts.ai.config import AIProviderConfig
from scripts.ai.providers.registry import provider_from_config

config = AIProviderConfig.from_environment()                    # defaults to mock
config = AIProviderConfig.from_environment(provider_preference="openai")
provider = provider_from_config(config)
```

Safety rules baked into the config:

- ``api_keys`` is excluded from the default ``__repr__`` and the
  custom ``__repr__`` redacts it.
- :meth:`safe_dict` returns a logging-safe snapshot that reports key
  *presence* (boolean) but never raw values.
- Unknown provider names are normalized to ``mock`` rather than raising
  so the app stays usable on typos.

### Switching providers

For local Ollama:

1. Install/start Ollama.
2. Pull the model named by `LOCAL_AI_MODEL`.
3. Set `ENABLE_LOCAL_AI_CALLS=true`.
4. Choose `Local AI runtime, Ollama` in Settings, or set
   `AI_PROVIDER_PREFERENCE=local`.
5. Generate drafts through the localhost app bridge.

For future cloud providers:

1. Add or update keys in your local ``.env``
   (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``).
2. Set cloud/network gates only when the provider adapter is implemented.
3. Change ``aiProviderPreference`` in app settings or set
   ``AI_PROVIDER_PREFERENCE=openai`` (etc.) in your environment.
4. The next call to ``provider_from_config(AIProviderConfig.from_environment(...))``
   will return the matching adapter.

## Safety Notes

- Mock provider is the default for development and tests.
- Local provider calls only localhost by default and is disabled unless
  `ENABLE_LOCAL_AI_CALLS=true`.
- Cloud provider adapters never import vendor SDKs at module load.
- Test suite mocks Ollama responses and does not call real external APIs by default.
- Provider metadata is safe to expose to the UI. It does not contain
  tokens, raw responses, or other secrets.
- The Settings UI must call `list_available_providers` rather than
  inspecting environment variables directly.

## Future Work

- Batch 3 Step 2: prompt registry with versioned templates.
- Batch 3 Step 3: safety review module.
- Batch 3 Step 4: content generation orchestrator that persists drafts
  to `generated_posts` and writes `approval_logs` records.
- A later batch will implement real provider calls behind the same
  gates, with retries, redaction, and tests.
