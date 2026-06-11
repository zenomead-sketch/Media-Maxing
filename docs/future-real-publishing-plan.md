# Future Real Publishing Plan

Real publishing should be implemented one platform at a time. Do not build broad autonomous publishing first.

This plan must preserve the local-first product model: local data, local approval, clear Manual Export fallback, and no hidden automation.

## Recommended starting point

Start with Meta only after real OAuth and account discovery are stable, or continue validating Manual Export until OAuth and platform requirements are fully understood.

## Required safety gates

- User approval is required.
- Draft must be approved.
- Editing an approved draft must require reapproval.
- Preflight must pass.
- Emergency pause must be off.
- Queue item must be in a publishable state.
- Platform account must be selected and healthy.
- Real publishing flag must be explicitly enabled.
- User must confirm the final action.

## OAuth/token hardening

- OAuth state must be random, hashed, short-lived, and one-time use.
- Tokens must not be logged.
- Tokens must not be exposed to frontend responses.
- Tokens should use OS keychain or encrypted local storage.
- Revocation, expiry, refresh, and requires-reauth flows must be tested.

## platform API verification

Before implementation, verify official platform docs for:

- Required scopes.
- Media formats.
- Caption/title/description limits.
- Account type requirements.
- App review requirements.
- Rate limits.
- Error codes.
- Sandbox/test mode availability.

## App review

Meta, TikTok, LinkedIn, YouTube, and X can require app review, product access, paid access, or verification. Do not claim a platform is production-ready until the required app review path is complete.

## user approval

The user must see:

- Platform.
- Account.
- Caption.
- Media.
- Safety flags.
- Preflight result.
- Final confirmation copy.

Approval must be local and auditable before any network publish call.

## Preflight

Preflight must check content, media, safety flags, account health, connection status, missing scopes, platform requirements, emergency pause, and queue status.

## post-publish audit log

Every publish attempt must write:

- Queue item ID.
- Scheduled post ID.
- Platform.
- Account ID.
- Attempt type.
- Started and finished timestamps.
- Status.
- Redacted provider result.
- Error code/message when failed.

## rollback/error handling

Publishing may fail after a network call. The app must show failure state, preserve local records, avoid duplicate retries by default, and guide the user to Manual Export if needed.

## rate limit handling

Rate limits must be treated as first-class errors. Add retry-after handling, backoff, and clear UI messages before real publishing is enabled.

## Required tests

- Publishing disabled by default.
- Missing approval blocks publish.
- Failed preflight blocks publish.
- Emergency pause blocks publish.
- Missing/expired/revoked account blocks publish.
- Missing scopes blocks publish.
- Rate limited response is safe.
- Provider auth error requires reauth.
- Provider response is redacted.
- Duplicate submit does not duplicate publish.
- Audit log is written for success and failure.

## Autonomous publishing should wait

Autonomous publishing should wait until manual approval publishing is boringly reliable. Complaints, urgent leads, sensitive content, platform policy changes, and business reputation risk make full automation unsafe at this stage.
