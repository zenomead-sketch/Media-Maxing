# Next Build Plan

This plan starts after the `0.1.0-local-test` local-first handoff. Choose one track at a time. Do not enable real publishing until the future real publishing plan is satisfied.

## Track A: Real Meta OAuth and account discovery

### Goal

Implement real Meta OAuth readiness and safe account discovery for Facebook Pages, Instagram Business/Creator accounts, and Threads profiles.

### Prerequisites

- Real Meta developer app.
- Verified redirect URI.
- Explicit real OAuth and real network flags.
- Token storage mode decision.
- Mock mode must remain default.

### Risks

- Token leakage.
- Incorrect scopes.
- App review requirements.
- Confusing mock accounts with real accounts.

### Recommended prompts

1. Audit Meta OAuth config and token storage.
2. Implement real OAuth callback with mocked tests first.
3. Add account discovery for Facebook Pages only.
4. Add Instagram account discovery after Facebook is stable.
5. Update Connected Accounts UI to distinguish mock, limited, and real.

### Acceptance criteria

- OAuth state is hashed and one-time use.
- Tokens are never exposed to frontend.
- Missing config fails safely.
- Mock OAuth still works.
- Real publishing remains disabled.

## Track B: Real publishing for one platform behind strict approval

### Goal

Enable the first real publishing path for one platform only, behind explicit user approval, preflight, emergency pause, and audit logs.

### Prerequisites

- Track A or equivalent real OAuth complete.
- Secure token storage.
- Official platform API limits verified.
- App review understood.
- Manual Export fallback remains available.

### Risks

- Accidental posting.
- Rate limit failures.
- Unclear rollback behavior.
- Platform policy changes.

### Recommended prompts

1. Re-audit `docs/future-real-publishing-plan.md`.
2. Choose one platform and verify official docs.
3. Add disabled-by-default publishing adapter tests.
4. Implement dry-run publishing preview.
5. Implement real publish only behind explicit safety flags and confirmation.

### Acceptance criteria

- Real publish cannot run unless every gate passes.
- Emergency pause blocks it.
- Approval and preflight are required.
- Post-publish audit log exists.
- Failed publish is recoverable and visible.

## Track C: Better AI generation and image/video analysis

### Goal

Improve content quality with richer prompts, optional real provider adapters, and media analysis for local business photos/videos.

### Prerequisites

- Prompt evaluation fixtures remain deterministic.
- Brand Brain and AI memory are populated.
- Privacy rules are clear before sending media externally.

### Risks

- Hallucinated claims.
- Privacy leakage in media analysis.
- Higher cost if real providers are used.
- Overfitting from weak analytics.

### Recommended prompts

1. Expand prompt evaluation cases.
2. Add local metadata-based media scoring.
3. Add optional provider adapter for text only.
4. Add explicit media privacy consent before external analysis.
5. Improve draft improvement suggestions.

### Acceptance criteria

- Mock provider still works.
- Structured output validation remains.
- Unsupported claims are flagged.
- Human approval remains required.
- Media privacy behavior is documented.

## Track D: Cloud sync or multi-device/team mode later

### Goal

Explore optional sync/team workflows without breaking local-first behavior.

### Prerequisites

- Local backup/restore is reliable.
- User identity and permissions are designed.
- Encryption and sync conflict strategy are defined.

### Risks

- Local-first promise becomes unclear.
- Secrets or customer data leak.
- Sync conflicts corrupt drafts or schedules.
- More support burden for non-coder users.

### Recommended prompts

1. Write cloud sync threat model.
2. Design optional sync architecture without implementation.
3. Add export/import improvements first.
4. Prototype sync using fake local remotes.
5. Revisit after desktop packaging is stable.

### Acceptance criteria

- Sync is optional.
- Local mode works without cloud.
- Sensitive data is encrypted or excluded.
- Conflicts are explainable and recoverable.
- Real publishing remains separately gated.
