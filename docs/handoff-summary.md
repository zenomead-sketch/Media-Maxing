# Handoff Summary

## Project purpose

This project is a local-first AI social media manager for small businesses and local service businesses. It helps a user turn real business context, job media, approvals, analytics, and engagement into safer social media workflows.

The current handoff is `0.1.0-local-test`. It is ready for local testing, not production SaaS. Real publishing is locked by default; guarded Facebook Page text posting exists for personal local testing only.

## Architecture summary

- `apps/web`: static HTML, CSS, and JavaScript UI.
- `apps/api`: Python standard-library localhost bridge for SQLite-backed browser workflows.
- `scripts`: Python SQLite services, migrations, local jobs, QA checks, and local utilities.
- `packages/types`: shared TypeScript domain types.
- `data`: local app data, media placeholders, logs, exports, backups, diagnostics, and SQLite databases.

The architecture is intentionally local-first. The app stores local data by default and avoids real external API calls in tests and normal mock-mode use.

## Tech stack

- Frontend: static web app.
- Backend/API: Python loopback server.
- Database: SQLite with raw SQL migrations.
- Jobs: lightweight Python local runner.
- AI: provider abstraction with mock provider as default.
- Connectors: scaffolded Python connector interfaces and mock OAuth.
- Desktop: packaging prep only; Tauri is the preferred future direction.

## App modules

- Control Center (`#home`) and setup checklist.
- Onboarding.
- Brand Brain.
- Media Library.
- Generate.
- Drafts.
- Calendar.
- Publish Queue.
- Connected Accounts.
- Social Integration Setup.
- Analytics.
- Engagement Inbox.
- Weekly Reports and AI Memory.
- Settings.
- Safety Center.
- Backup & Data.
- Diagnostics.

## Data storage

SQLite stores Brand Brain, media metadata, generated drafts, scheduled posts, queue items, attempts, approvals, social account metadata, OAuth state hashes, analytics, engagement items, reply suggestions, AI memory, weekly reports, onboarding state, and safety audit logs.

Local files live under `data/`. Exports go under `data/exports/`. Backups go under `data/exports/backups/`. Diagnostic reports go under `data/exports/diagnostics/`.

## Safety model

- Generated drafts default to review.
- Human approval is required.
- Scheduling only accepts approved safe drafts.
- Preflight blocks critical safety issues.
- Emergency pause blocks scheduling, queue readiness, mock publishing, future real publishing, future real replies, and unsafe automation.
- Manual Export is the safe posting path.
- Real publishing is locked by default, except guarded Facebook Page text posting after explicit setup.

## AI model/provider model

The default provider is mock. Real OpenAI, Anthropic, or local providers are future paths and must be explicitly configured. Prompt templates are versioned, structured outputs are preferred, and AI memory is evidence-backed with confidence labels.

## Social connector model

Connectors exist for Facebook, Instagram, Threads, YouTube, TikTok, LinkedIn, and X. Current connectors are scaffolded, mock-ready, or guarded behind safety flags. Publishing methods remain disabled by policy.

## Current limitations

See `docs/known-limitations.md`. The biggest limits are no real publishing, no real reply sending, no real analytics/comment fetching by default, no production desktop installer, and local scheduling that only processes while the app/backend/runner is active.

## How to continue development

1. Run the launch checks.
2. Pick one track from `docs/next-build-plan.md`.
3. Keep changes small and testable.
4. Keep mock mode working.
5. Update docs with every behavior change.
6. Do not enable real publishing without the future real publishing plan.

## Where important files live

- `AGENTS.md`: product rules and non-negotiable safety policy.
- `README.md`: quick start and docs index.
- `.env.example`: safe environment variable template.
- `scripts/db/migrations`: SQLite migrations.
- `scripts/db/seed_demo.py`: demo data.
- `scripts/services`: business services.
- `scripts/connectors`: social connector scaffolds.
- `scripts/jobs/local_runner.py`: local job runner.
- `scripts/launch_check.py`: launch candidate QA smoke check.
- `docs/launch-candidate-checklist.md`: full QA checklist.

## Commands to know

```powershell
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
python -m scripts.jobs.local_runner --database data/app.sqlite --once
python -m scripts.launch_check
python -m unittest discover tests
python -m scripts.qa.integration_security_scan .
```
