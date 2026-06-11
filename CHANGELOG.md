# Changelog

## 0.1.0-local-test - Local Test Release

This is the first organized local-first handoff build. It is intended for local testing with mock/demo data, manual export, and human approval. Real publishing remains disabled.

### Added

- Initial local-first app foundation with static web shell, Python localhost bridge, SQLite migrations, seed data, and documentation.
- Brand Brain for business identity, services, service areas, voice, CTA, and safety context.
- Media Library for local media metadata, filtering, import records, and demo media.
- AI mock generation with provider abstraction, prompt registry, structured schemas, safety review, and prompt evaluation fixtures.
- Draft approvals with generated post persistence, editing, approve/reject/revision/archive actions, and approval logs.
- Calendar for local scheduled posts, rescheduling, cancellation, and detail review.
- Publish Queue for local readiness states, preflight results, mock/manual labels, and local queue actions.
- Manual Export packages with caption, hashtags, post markdown, metadata, media manifest, and posting instructions.
- Connector scaffolding for Facebook, Instagram, Threads, YouTube, TikTok, LinkedIn, and X.
- Connected Accounts mock mode, OAuth state scaffolding, token-safe DTOs, setup wizard, and connector health checks.
- Analytics with manual snapshots, mock analytics, performance summaries, breakdowns, rankings, and insights.
- Engagement Inbox with mock engagement ingestion, triage statuses, sentiment/intent/priority, and local action workflow.
- Reply suggestions with mock AI provider, Brand Brain context, safety flags, recommended actions, and local approval requirements.
- AI learning loop with evidence-backed AI memory, confidence rules, and weekly reports.
- Safety Center with emergency pause, automation levels, kill switch actions, blocked/allowed action summaries, and safety audit logs.
- Backup and Diagnostics tools for local backups, restore previews, redacted diagnostics, and safety reports.
- Desktop packaging prep with a Tauri-preferred direction, Python preview launcher, and packaging documentation.

### Safety Notes

- Real publishing is not implemented.
- Real replies are not sent.
- Real analytics and real comments are not fetched by default.
- Mock mode and manual export remain the safe local path.
- Launch checks currently report a partial status because there is no package-manager build script or production desktop installer yet.
