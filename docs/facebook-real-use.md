# Facebook Real-Use Readiness

This guide explains the first safe path for using a real Facebook connection with Media Maxing.

Facebook real OAuth, Page discovery, and a first guarded Facebook text or single-image post path are prepared for local testing. Real publishing is still disabled by default. It only runs when you explicitly configure real OAuth, real network calls, real publishing flags, a Facebook Page token, a ready Publish Queue item, and the typed confirmation phrase.

The local API also issues a fresh one-time publish nonce when the browser checks Facebook posting readiness. The Publish Queue sends that nonce back with the typed confirmation phrase. This is an extra local safety check; the real protection is still the server-side gate that verifies flags, preflight, account scopes, Page token availability, emergency pause, and queue state.

## What Works Now

- Build a real Meta OAuth authorization URL for Facebook when real OAuth flags are enabled.
- Validate OAuth state with one-time hashed state records.
- Exchange an authorization code through the guarded server-side HTTP client when all flags and config are present.
- Create a safe local connected account record.
- Run Facebook Page discovery checks through the connector health path.
- Understand `/me/accounts` style Page discovery responses.
- Redact Page access tokens from logs, debug output, and UI-safe DTOs.
- Keep Manual Export as the default safe posting path.
- Publish a Facebook Page text post, or one linked local image with the generated caption, only through the guarded Publish Queue action after all safety gates pass.

## What Is Still Disabled

- Instagram, Threads, YouTube, TikTok, LinkedIn, and X real posting.
- Facebook multi-image, carousel, and video publishing.
- Facebook auto-posting or batch publishing.
- Auto-posting.
- Comment replies.
- Broad analytics fetching by default. Guarded Meta analytics sync is documented separately and still requires explicit setup.
- Token refresh.
- Long-lived token exchange.
- Production-grade secure token storage.

## Create The Meta App

1. Go to Meta for Developers and create or select an app.
2. Add Facebook Login or Facebook Login for Business, depending on your app setup.
3. Add the redirect URI for the local API you are actually running.

If you use the default all-local beta launcher, use:

```text
http://127.0.0.1:8044/api/connect/facebook/callback
```

If you use the Vercel UI with the local companion launcher, or you run
`apps.api.local_server --port 8000`, use:

```text
http://localhost:8000/api/connect/facebook/callback
```

If you use Vercel only for the frontend, the redirect is still the local companion API callback, not the Vercel page URL. The URL in Meta, `.env`, and the local API start flow must match exactly.

4. Add the Facebook Page permissions needed for the guarded connection and posting path:

```text
pages_show_list
pages_manage_metadata
pages_read_engagement
pages_manage_posts
```

Do not rely on these permissions until your Meta app is configured correctly and you are testing on a Page you control. If you previously connected without one of these permissions, use **Reconnect real** in Connected Accounts. The app includes Meta's permission re-request parameter so the provider can ask again for missing or declined scopes.

## Configure `.env`

Copy `.env.example` to `.env`, then set:

```env
INTEGRATIONS_MODE=real_oauth
ENABLE_REAL_OAUTH=true
ENABLE_REAL_NETWORK_CALLS=true
ENABLE_REAL_PUBLISHING=false
TOKEN_STORAGE_MODE=placeholder_not_stored

META_CLIENT_ID=your-meta-client-id
META_CLIENT_SECRET=your-meta-client-secret
META_REDIRECT_URI=http://127.0.0.1:8044/api/connect/facebook/callback
META_GRAPH_API_VERSION=v25.0
META_ENABLE_REAL_OAUTH=true
META_ENABLE_REAL_PUBLISHING=false
```

Never commit `.env`.

Use the same `META_REDIRECT_URI` value that you added in the Meta developer app. For Vercel UI plus local companion mode, that is usually `http://localhost:8000/api/connect/facebook/callback`.

## Do Not Add The Facebook JavaScript SDK

Do not paste the Facebook JavaScript SDK snippet into this app. Media Maxing uses a server-side OAuth redirect through the local Python API so the client secret, authorization code, access tokens, and Page tokens stay out of the browser.

For guarded Facebook post testing, you must intentionally change both publishing flags:

```env
ENABLE_REAL_PUBLISHING=true
META_ENABLE_REAL_PUBLISHING=true
```

Do not enable these until you have read this guide, connected a test Facebook Page, confirmed emergency pause is off, and confirmed you are ready for the app to create a real Page post.

## Token Storage Warning

The safe default is:

```env
TOKEN_STORAGE_MODE=placeholder_not_stored
```

This refuses raw tokens. It is safest, but it means the app cannot make later real provider calls after OAuth unless secure token storage is implemented.

For local developer testing only, an insecure mode exists:

```env
APP_ENV=development
TOKEN_STORAGE_MODE=insecure_dev_only
ALLOW_INSECURE_TOKEN_STORAGE=true
```

Use that only on a private local machine with throwaway/test credentials. It stores token values locally and is not production-safe.

The current guarded Facebook post service requires this development-only token mode because OS keychain/encrypted token storage is not implemented yet. That is acceptable for personal local testing only, not production.

## Test The Connection

1. Start the local app/API.
2. Open **Control Center**.
3. Review **Facebook posting setup**. This panel checks the local API, feature flags, Facebook Page account, required Page permissions, token storage, ready queue item, and final confirmation gate.
4. If the panel says the account is mock/demo, open **Connected Accounts**.
5. Confirm Facebook shows **Connect real** enabled. If it is disabled, open **Social Integration Setup** and fix the missing env vars or flags first.
6. Click **Connect real** for Facebook. This starts server-side OAuth through the local API and redirects to Meta.
7. Complete the Meta login in the browser and allow the required Page permissions.
8. Return to the app and run **Check connection**.

Expected safe result:

- A Facebook account appears locally.
- The health check can identify a Page when mocked or when real discovery has a usable token.
- No token values appear in the UI.
- Real publishing remains locked unless the publishing flags and queue gates are explicitly enabled.
- Demo/mock Facebook accounts are clearly blocked from real posting.

## Publishing A Facebook Post With Caption And Media

The app now supports:

- Caption-only Facebook Page text posts.
- One linked local image uploaded as a Facebook Page photo post with the generated caption.

The app does not yet support multi-image albums, carousels, reels, videos, or stories. If a scheduled Facebook item has more than one linked media asset, or if the linked asset is a video, use **Manual Export** for now.

Before using **Publish to Facebook (real)** in Publish Queue, confirm:

1. The draft was generated, reviewed, and approved.
2. The approved draft was scheduled locally.
3. The Publish Queue item is `ready`.
4. Preflight is `passed` or `warnings`, with no blocking errors.
5. The connected account is a real Facebook Page account, not a demo/mock account.
6. The connected Page has required scopes:
   - `pages_show_list`
   - `pages_manage_metadata`
   - `pages_read_engagement`
   - `pages_manage_posts`
7. Emergency pause is off.
8. The local API bridge is running.
9. The queue item has a caption snapshot.
10. If media should be included, the scheduled item has exactly one linked image file in the local Media Library.
11. You are willing to create a real Facebook Page post.

The app then asks you to type:

```text
PUBLISH TO FACEBOOK
```

If the phrase does not match exactly, nothing posts. If a gate fails, nothing posts.

On success, the app records:

- `publish_queue_items.queue_status = platform_published`
- `scheduled_posts.status = completed`
- a `published_posts` row with `publish_mode = platform_api`
- a `publish_attempts` row with `attempt_type = future_real_publish`
- an approval/audit log entry

If one linked image is present, the connector uses the Facebook Page photo endpoint. If no media is linked, it uses the Page feed text endpoint.

## Manual Export Remains The Default Posting Path

After you approve and schedule a Facebook draft, use **Manual Export** from Publish Queue if you want to review the package manually, include multiple images, include video, or avoid real API posting. That creates a local posting package with caption, hashtags, media references, and instructions.

Do not treat a connected Facebook account as permission to post automatically. Real posting must always go through the guarded queue action and typed confirmation.

## Sources To Re-Check Before Publishing

Meta documentation changes. Before relying on real Facebook posting, verify:

- Current Graph API version.
- Pages API feed and photo publishing endpoints.
- Required Page permissions.
- Page access token behavior.
- App review requirements.
- Rate limits and error codes.

As of June 24, 2026, current public Meta docs indicate the Graph API latest version is `v25.0`, the Pages API supports Page content operations, and Pages API setup uses Page listing/access-token flows. Verify again before serious use.

## Verification Commands

```text
python -m unittest tests.test_meta_oauth_exchange_readiness tests.test_meta_account_health tests.test_meta_connectors tests.test_facebook_real_publishing
python -m scripts.qa.integration_security_scan .
```

These tests use mocked provider responses. They do not call real Meta APIs.
