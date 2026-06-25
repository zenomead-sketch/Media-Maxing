# Connected Accounts

Connected Accounts is the local setup area for social platform integrations.

Mock/demo mode remains the default. Facebook can also start a real server-side OAuth flow when the local API, Meta credentials, and real OAuth flags are ready. Guarded Facebook Page text or single-image posting is still separate from connecting: it only runs through Publish Queue after preflight, emergency pause checks, server-side Page token availability, and typed confirmation.

## What Works Now

- Platform cards exist for Facebook, Instagram, Threads, YouTube, TikTok, LinkedIn, and X.
- Facebook and Instagram can be mock connected from the browser UI.
- Facebook can start real OAuth from **Connect real** when setup is ready.
- Mock connected accounts persist locally; localhost mode persists accounts to SQLite through the local API.
- Disconnect marks a mock account disconnected locally.
- Check connection validates mock/local health status and records a safe audit event.
- A small local audit log records mock connect and disconnect events.
- The UI shows only safe account details.
- Publish Queue preflight can use connected account status as a local readiness signal.

## What Is Still Disabled Or Guarded

- Instagram, Threads, YouTube, TikTok, LinkedIn, and X real posting remain disabled.
- Facebook real OAuth and Page discovery require explicit flags and server-side local API handling.
- Facebook real posting is limited to the guarded Publish Queue path for Page text or one linked image.
- Real comments and replies are not fetched or sent.
- Broad analytics fetching remains disabled by default; guarded Meta analytics sync is documented separately.
- Facebook Page discovery can fetch Page profile metadata only after real OAuth setup is enabled.
- No real credentials are required.

## Account Statuses

Connected account records can use these statuses:

- `not_connected`
- `connecting`
- `connected`
- `limited`
- `expired`
- `revoked`
- `disconnected`
- `error`
- `requires_reauth`

Only `connected` and some `limited` mock/demo accounts are useful for local readiness display. For guarded Facebook posting, the account must be a real connected Facebook Page with a server-side Page token. Expired, revoked, disconnected, error, and requires-reauth accounts do not satisfy future real publishing readiness.

## Token Safety

The browser UI must not show or store platform secret values. The current mock connection records use `placeholder_not_stored` for storage mode.

Real OAuth work uses the server-side OAuth state service and token security service. Today this is usable for the guarded Facebook path when configured; other platforms remain scaffolded. Frontend responses should only include safe account DTO fields such as display name, platform, status, scopes, and timestamps.

## Mock Connect Flow

1. Open Connected Accounts.
2. Choose **Connect mock** for Facebook or Instagram.
3. The app creates a fake local account record.
4. The account appears in the connected account list.
5. Real publishing remains locked by default. Facebook Page text or single-image posting requires the guarded Publish Queue action, explicit flags, preflight, and typed confirmation.

## Real Facebook Connect Flow

1. Finish `docs/facebook-real-use.md`.
2. Start the local API bridge.
3. Open Connected Accounts.
4. Choose **Connect real** for Facebook.
5. Complete Meta login and allow the Page permissions.
6. Return to Connected Accounts and choose **Check connection** if needed.

The browser never receives the client secret, raw authorization code, access token, refresh token, or Page token.

## Disconnect Flow

1. Choose **Disconnect** on a mock account.
2. Confirm the local disconnect.
3. The account is marked disconnected.
4. A local audit entry is created.
5. No external revoke is attempted.

## Reauth And Missing Scopes

Reauth is needed when an account is expired, revoked, disconnected, in error, or explicitly marked `requires_reauth`.

Missing scopes are stored as safe metadata. They tell the user what a future OAuth setup may need. Missing scopes do not expose tokens and do not block manual export by themselves.

## Health Checks

Connected Accounts includes a **Check connection** action. In the current static web app this is a mock/local check only. It updates health status, last validated time, missing permissions, warnings, and audit history in local browser storage.

The Python Meta connectors also expose `validateConnection()` and `getAccountProfile()` for server-side health scaffolding. Those methods can use mocked provider responses in tests and update local SQLite records. Real provider discovery remains gated and disabled by default.

## Publish Queue Readiness

Connected account status is shown in Publish Queue cards and detail panels.

Current rules:

- Missing account: warning only for manual export; future real publishing would be blocked.
- Mock connected account: satisfies mock/demo account checks, but cannot publish for real.
- Real connected Facebook Page: can satisfy the guarded Facebook posting account gate only when scopes and server-side Page token storage are available.
- Expired, revoked, error, or requires-reauth account: warning in the UI and future real publishing blocked.
- Limited account: shown with missing scopes or setup warnings.
- Multiple accounts for one platform: the app uses a safe local default and warns that account selection will be needed later.

Manual export remains the fallback when content preflight passes. No tokens are shown and no platform API calls are made.

## Future Work

- Add account selection when multiple Facebook Pages are returned.
- Add secure keychain/encrypted token storage so local development no longer needs explicit insecure dev token mode.
- Keep every non-Facebook real publishing path disabled until each platform gets its own safety gates, tests, and documentation.

## How To Test

Run:

```text
python -m unittest tests.test_social_connection_models tests.test_web_connected_accounts_screen
python -m unittest tests.test_meta_account_health
```

These tests cover safe mock account storage, placeholder token rows, safe frontend DTOs, browser UI token-field exclusions, and Connected Accounts screen wiring.
