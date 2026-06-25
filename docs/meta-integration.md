# Meta Integration Scaffold

This document describes the current Meta connector scaffold for Facebook, Instagram, and Threads.

The Meta layer is safe by default. It does not fetch comments, send replies, fetch broad analytics, or call Meta APIs unless explicit flags are enabled. A guarded OAuth and Facebook Page discovery path exists for local testing, and a narrow Facebook Page text or single-image posting path exists through Publish Queue. Instagram, Threads, broad Meta publishing, and autonomous posting remain disabled.

## Connector Modules

Meta connector code lives under `scripts/connectors/meta/`:

- `facebook.py`: Facebook Page connector scaffold.
- `instagram.py`: Instagram Business/Creator connector scaffold.
- `threads.py`: Threads connector scaffold.
- `config.py`: safe Meta environment configuration loader.
- `oauth.py`: mock authorization URL helpers, real authorization URL helpers, and guarded token exchange request building.
- `oauth.py`: also contains the centralized profile discovery request scaffold, marked TODO for API verification.
- `errors.py`: normalized, redacted Meta error shapes.
- `base.py`: shared Meta connector behavior.

The central registry in `scripts/connectors/registry.py` returns these connectors for:

- `facebook`
- `instagram`
- `threads`

## Environment Variables

The config loader reads:

```text
META_CLIENT_ID=
META_CLIENT_SECRET=
META_REDIRECT_URI=
META_GRAPH_API_VERSION=
META_ENABLE_REAL_OAUTH=false
META_ENABLE_REAL_PUBLISHING=false
```

`META_GRAPH_API_VERSION` defaults to `v25.0` when unset. Meta versions and permission behavior change over time, so verify the current official docs before live use.

The loader only exposes whether `META_CLIENT_SECRET` is configured. It should not print, log, or return the secret value.

## OAuth Behavior

Mock mode can build a local mock authorization URL without credentials.

Real OAuth token exchange is setup-gated:

- missing `META_CLIENT_ID`, `META_CLIENT_SECRET`, or `META_REDIRECT_URI` returns `setup_required`
- real OAuth requires `ENABLE_REAL_OAUTH=true` or `INTEGRATIONS_MODE=real_oauth`
- real OAuth also requires `ENABLE_REAL_NETWORK_CALLS=true`
- real OAuth also requires `META_ENABLE_REAL_OAUTH=true`
- OAuth state must be validated by `OAuthFlowService`
- the callback must include an authorization code
- the server-only platform HTTP client must allow the request

If any requirement is missing, no network call is made and the callback returns a safe setup/disabled result.

When all gates pass, `OAuthFlowService` builds a real Meta authorization URL during start, stores only a hash of the OAuth state, and later builds the documented Meta `GET /oauth/access_token` request through `scripts/connectors/meta/oauth.py`. Token exchange goes through `scripts/services/platform_http_client.py`. Tests use mocked HTTP responses only.

## Token And Account Behavior

The token response is passed to `TokenSecurityService`.

With the current default:

```text
TOKEN_STORAGE_MODE=placeholder_not_stored
```

raw token values are refused and are not stored. The app stores placeholder token metadata only, with null token blob fields.

With placeholder storage, a successful token exchange creates or keeps a limited local account:

- `connectionStatus=limited`
- `platformAccountId` may use an unknown local placeholder or discovered Page ID
- `requiresReauth=true`
- safe frontend DTO only
- warning that token storage is not publish-ready

For Facebook only, explicit local development token storage can now run Page discovery through `/me/accounts`, store a Page token through `TokenSecurityService`, and promote the account to:

- `connectionStatus=connected`
- `accountType=page`
- real Page ID as `platformAccountId`
- `requiresReauth=false`
- safe frontend DTO only

This path still requires `APP_ENV=development`, `TOKEN_STORAGE_MODE=insecure_dev_only`, and `ALLOW_INSECURE_TOKEN_STORAGE=true`. It is for local personal testing only until keychain or encrypted storage exists.

Long-lived token exchange is not implemented yet. That future step must verify current Meta docs, token lifetimes, app review requirements, and secure token storage first.

## Account Discovery And Health

Meta connectors now expose:

- `getAccountProfile()`
- `validateConnection()`

The current discovery path is a safe scaffold. Facebook discovery is shaped for Page discovery through `/me/accounts` and can read a mocked response containing Page IDs, names, usernames, categories, tasks, and Page access tokens. Page access tokens are redacted and are not exposed to the UI. Tests inject mocked provider responses through the server-only platform HTTP client. Real discovery is not called by default; it requires real OAuth/network flags and server-side execution.

Health checks can return:

- `healthy`
- `limited`
- `expired`
- `missing_permissions`
- `network_disabled`
- `error`

Health checks update `last_validated_at`, store safe connector health rows, and write safe audit logs. Provider auth failures such as HTTP 401 map to `expired` and `requires_reauth`. Missing scopes map to `missing_permissions`. Network-disabled mode returns a safe health result instead of crashing.

## Publishing Behavior

Broad Meta publishing is disabled by policy.

`META_ENABLE_REAL_PUBLISHING=true` does not enable generic connector publishing. Meta connector publishing methods return `disabled_by_policy` and report `realPublishingEnabled=false`. The current exception is the separate guarded Facebook Page text or single-image Publish Queue service.

Real publishing requires a future explicit platform task with:

- real OAuth
- secure token storage
- verified Meta API docs
- app review requirements understood
- account selection
- platform preflight tests
- approval gates
- emergency pause enforcement
- post-publish audit logs
- manual export fallback
- explicit user confirmation

## Setup Instructions

Each connector exposes setup instructions for:

- Meta developer app setup
- redirect URI
- placeholder scopes
- required account type
- app review warning
- local development notes
- publishing-disabled safety notice

Current Facebook connection scopes for the guarded Page path are `pages_show_list`, `pages_manage_metadata`, `pages_read_engagement`, and `pages_manage_posts`. These scopes only make the server-side Facebook Page connection usable; they do not allow broad or automatic publishing. The guarded Publish Queue action still requires preflight, emergency pause off, a connected Page token, explicit real-publishing flags, and typed confirmation.

## Practical Setup Checklist

For later real OAuth work:

1. Create or select a Meta developer app.
2. Add the local callback URL as `META_REDIRECT_URI`.
3. Add `META_CLIENT_ID` and `META_CLIENT_SECRET` only to local `.env`, never to committed files.
4. Keep `META_ENABLE_REAL_OAUTH=false` until the guarded real OAuth task begins.
5. Keep `META_ENABLE_REAL_PUBLISHING=false`; this flag does not enable publishing in Batch 6.
6. Confirm whether the Facebook Page, Instagram Business/Creator account, or Threads profile requires app review.
7. Run mock OAuth and Connected Accounts tests before touching real credentials.
8. Update docs with verified official API requirements before making network calls.

## Error Handling

Meta errors are normalized into a safe shape:

- `code`
- `message`
- `userSafeMessage`
- `retryable`
- `requiresReauth`
- `missingConfig`
- `rawErrorRedacted`

Raw provider details are redacted before storage or display. Do not log authorization codes, token values, bearer values, or client secrets.

## How To Test

Run:

```text
python -m unittest tests.test_meta_connectors
python -m unittest tests.test_meta_oauth_exchange_readiness
python -m unittest tests.test_meta_account_health
```

These tests cover missing config, mock authorization URL generation, setup instructions, disabled publishing behavior, redacted Meta error normalization, guarded token exchange, placeholder token storage, safe account DTOs, and provider 401/429 handling.
