# AI Learning Loop

The AI learning loop is a local, evidence-backed memory service. It helps the app remember useful patterns without turning weak signals into business claims.

The stable public facade lives in `scripts/services/ai_learning.py`. Evidence
extraction and memory persistence live in `scripts/services/ai_memory.py`.

## What It Learns From

`AIMemoryService.refresh_from_local_evidence()` can create or refresh memory from:

- Brand Brain services, supported claims, and blocked-phrase guardrails.
- Active `content_insights` produced from local analytics.
- Local `post_performance_metrics`.
- Current approved, rejected, and revision-requested draft state.
- Draft approval logs.
- Draft rejection, revision, and reapproval logs.
- Direct local engagement patterns such as complaints, pricing questions, and lead questions.
- Local reply approval, rejection, escalation, spam, and manual-handling audits.
- Reviewed local media metadata and content-angle tags.

Memory records use stable IDs for derived evidence. Running the refresh twice updates the same records instead of creating duplicate learning noise.

## Evidence And Privacy

Each derived memory stores evidence IDs and counts. Engagement learning stores
`engagement_items` and `reply_approvals` IDs, not private comment or message
text.

Every memory includes:

- A memory type.
- A short title.
- A plain-language summary.
- Evidence references.
- Confidence: `low`, `medium`, or `high`.
- Source provenance.
- Status: `active`, `dismissed`, `archived`, or `superseded`.

Mock analytics produce `source = mock` memory. A mock-derived memory must stay visibly mock throughout the loop.

## Generation Context

When the Generate screen runs through the localhost bridge, the content
generation service loads up to eight active memory records for the selected
brand. It passes bounded title, summary, confidence, type, and source fields
into the prompt context and records the same safe summaries in prompt
metadata.

Raw engagement content is not added to the prompt through this loop. Memory is
guidance, not a new business claim, and generated drafts still require owner
review.

`AILearningService.applyLearningToGenerationContext()` returns at most eight
active memories by default. It also returns local-only metadata so callers can
verify that no private data was sent externally.

## Confidence Rules

- Fewer than 5 relevant records: `low`.
- 5 to 20 relevant records: `medium`.
- More than 20 relevant records: `high` only when the pattern is also consistent.
- More than 20 mixed records remain `medium`.

Confidence labels describe local evidence strength. They never turn a pattern
into a promise, guarantee, or unsupported business claim.

## Conservative Behavior

The learning loop does not:

- Call an external AI provider.
- Call social platform APIs.
- Send replies.
- Publish posts.
- Delete memory automatically.
- Treat owner approval as proof of performance.
- Turn a small sample into a guarantee.

Memory can be dismissed or archived without deleting its audit value. A
dismissed or archived memory is not included in future generation context.

## Public Service Methods

`AILearningService` exposes:

- `generateContentInsights()`
- `updateLearningMemory()`
- `generateWeeklyReport()`
- `getActiveLearningMemory()`
- `applyLearningToGenerationContext()`
- `dismissMemory()`
- `archiveMemory()`

## Run A Local Refresh

```text
python -m scripts.services.ai_memory --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care
```

The command prints the refreshed records and explicit `external_ai_calls=false` and `external_platform_calls=false` markers.

To refresh memory and generate a weekly report together:

```text
python -m scripts.services.ai_learning --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care --week-start-date 2026-06-08
```

## Review Memory In The App

Open Analytics and use **Weekly review and AI memory**. The owner can refresh
memory from local evidence, inspect the active summaries used by future draft
generation, and dismiss or archive a record without deleting it.

Superseding a memory record remains future work.
