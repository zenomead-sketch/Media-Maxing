# AI Learning Loop

The AI learning loop is a local, evidence-backed memory service. It helps the app remember useful patterns without turning weak signals into business claims.

The service lives in `scripts/services/ai_memory.py`.

## What It Learns From

`AIMemoryService.refresh_from_local_evidence()` can create or refresh memory from:

- Active `content_insights` produced from local analytics.
- Draft approval logs.
- Draft rejection, revision, and reapproval logs.
- Local reply approval, rejection, escalation, spam, and manual-handling audits.

Memory records use stable IDs for derived evidence. Running the refresh twice updates the same records instead of creating duplicate learning noise.

## Evidence And Privacy

Each derived memory stores evidence IDs and counts. Engagement learning stores `reply_approvals` IDs, not private comment or message text.

Every memory includes:

- A memory type.
- A short title.
- A plain-language summary.
- Evidence references.
- Confidence: `low`, `medium`, or `high`.
- Source provenance.
- Status: `active`, `archived`, or `superseded`.

Mock analytics produce `source = mock` memory. A mock-derived memory must stay visibly mock throughout the loop.

## Conservative Behavior

The learning loop does not:

- Call an external AI provider.
- Call social platform APIs.
- Send replies.
- Publish posts.
- Delete memory automatically.
- Treat owner approval as proof of performance.
- Turn a small sample into a guarantee.

Manual memory can be archived without deleting its audit value.

## Run A Local Refresh

```text
python -m scripts.services.ai_memory --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care
```

The command prints the refreshed records and explicit `external_ai_calls=false` and `external_platform_calls=false` markers.

## Future UI Work

A later UI can let the owner review, archive, and supersede memory records. The current service layer is ready for that screen and for future prompt context selection.
