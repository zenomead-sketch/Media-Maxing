# Media-Maxing

A local-first AI social media manager for small businesses, local service businesses, and owner-operators.

Release label: `0.1.0-local-test`

This project has a local-first MVP foundation with a static web shell, SQLite
services, and a localhost bridge. It does not publish real posts, send real
replies, or connect real platform APIs by default.

Real publishing remains disabled by default. A guarded Facebook Page text or single-image post path exists for personal local testing only when explicit flags, Page permissions, preflight, and typed confirmation all pass.

## Quick Start

For the easiest local beta path on Windows, double-click:

```text
start-media-maxing.bat
```

Or run the same launcher from a terminal:

```text
python -m scripts.local_beta_launcher
```

This starts the local API and web app together and opens Control Center at
`http://127.0.0.1:8044/#home`. Real replies and most social APIs stay disabled; guarded Facebook Page text or single-image publishing stays locked unless you explicitly enable the flags described in `docs/facebook-real-use.md`.

To practice with clearly fake demo data:

```text
python -m scripts.local_beta_launcher --seed-demo
```

Advanced/manual startup:

```text
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Then open `http://127.0.0.1:8000`.

Start with the Intro Setup Guide or Onboarding for a fresh database, or use seeded demo data to explore the Control Center, Brand Brain, Media Library, Generate, Drafts, Calendar, Publish Queue, Analytics, Engagement Inbox, Safety Center, Backup & Data, and Diagnostics.

## Launch candidate status

Current status: partial local test release.

What passed in the latest launch check:

- Database and seed smoke.
- Core local workflow smoke.
- Safety workflow smoke.
- Backup and diagnostics export scan.
- Redacted security scan.
- Unit tests, Python compile checks, and web JavaScript syntax checks.

Why it is partial:

- There is no `package.json` or frontend build command yet.
- There is no production desktop installer yet.
- A final human browser QA pass is still required before broader testing.

Run the launch checks:

```text
python -m scripts.launch_check
python -m scripts.demo_day_check
python -m scripts.qa.integration_security_scan .
```

## Mock Mode

Mock mode is the default safe path. It supports mock AI generation, mock OAuth, mock analytics, mock engagement, and local-only workflow testing without API keys.

## Local Or Cloud Generation

Generation now has three paths:

- `mock`: default, offline, deterministic, best for testing.
- `local`: Ollama-compatible local generation on your machine. Install/start
  Ollama separately, pull the model in `LOCAL_AI_MODEL`, set
  `ENABLE_LOCAL_AI_CALLS=true`, and choose `Local AI runtime, Ollama` in
  Settings.
- `cloud`: OpenAI/Anthropic placeholders remain scaffolded for later. They are
  not enabled by default and should only be used after explicit provider setup,
  cost/privacy review, and tests.

Real social publishing and real reply sending remain disabled regardless of
which generator mode is selected.

Manual Export is the safe posting path. It creates local posting packages and does not publish automatically.

## Guarded Facebook Posting

The first real posting path is intentionally narrow: Facebook Page posts only.
It can publish either:

- A generated caption as a Facebook Page text post.
- A generated caption plus exactly one linked local image as a Facebook Page photo post.

It does not support Facebook video, albums, carousels, reels, stories, personal profile posts, comments, DMs, or autonomous/batch publishing.

Real Facebook posting is disabled by default and requires all of these gates:

- Real OAuth/network/publishing flags enabled in `.env`.
- A connected Facebook Page account.
- Page permissions including `pages_manage_posts`.
- A ready Publish Queue item for Facebook.
- Passed or warning-only preflight.
- Emergency pause off.
- Local API bridge running.
- The exact typed confirmation phrase: `PUBLISH TO FACEBOOK`.

For image posts, the approved scheduled item must have exactly one linked local image in Media Library. The backend uploads that image from local storage to the Facebook Page photo endpoint with the generated caption. Multiple images or video should use **Manual Export** until those paths are built deliberately.

See `docs/facebook-real-use.md` for the setup checklist, required environment flags, token-storage warning, and verification commands.

## Main workflows

1. Create or confirm Brand Brain.
2. Add or seed Media Library items.
3. Generate mock drafts.
4. Save drafts to Drafts.
5. Approve safe drafts locally.
6. Schedule approved drafts on Calendar.
7. Run local jobs and preflight.
8. Use Publish Queue and Manual Export.
9. Optionally use guarded Facebook posting for approved Facebook queue items after real setup.
10. Add manual analytics or generate mock analytics.
11. Generate mock engagement and local reply suggestions.
12. Approve replies locally only.
13. Generate AI memory and weekly reports.
14. Use Safety Center, Backup & Data, and Diagnostics before launch testing.

## Safety statement

The app is designed around approval required, local-first data, mock mode, manual export, and emergency pause. Real reply sending is not implemented. Real publishing is disabled by default; the only current real publish path is guarded Facebook Page text or single-image posting for personal testing, with explicit environment flags, preflight, a connected Page, typed confirmation, audit logs, and tests.

## Final handoff docs

- `CHANGELOG.md`
- `RELEASE_NOTES.md`
- `TODO.md`
- `docs/handoff-summary.md`
- `docs/next-build-plan.md`
- `docs/known-limitations.md`
- `docs/future-real-publishing-plan.md`
- `docs/launch-candidate-checklist.md`

## Docs index

- Getting started: `docs/non-coder-setup.md`
- Intro setup guide: `docs/intro-setup-guide.md`
- User guide: `docs/user-guide.md`
- Operator manual: `docs/operator-manual.md`
- Common workflows: `docs/common-workflows.md`
- Troubleshooting: `docs/troubleshooting.md`
- Privacy and local data: `docs/privacy-and-local-data.md`
- Safety controls: `docs/safety-controls.md`
- Backup and Data: `docs/backup-and-data.md`
- Diagnostics: `docs/diagnostics.md`
- Desktop packaging: `docs/desktop-packaging.md`
- Glossary: `docs/glossary.md`
- Handoff summary: `docs/handoff-summary.md`
- Next build plan: `docs/next-build-plan.md`
- Known limitations: `docs/known-limitations.md`
- Future real publishing plan: `docs/future-real-publishing-plan.md`
- Facebook real-use readiness: `docs/facebook-real-use.md`
- Launch checklist: `docs/launch-candidate-checklist.md`

## Project Purpose

The goal is to build a safe local AI command center that helps a business turn its own photos, videos, brand context, and performance history into reviewed social media content.

The app is intended to help non-developer users:

- Define a business identity in a Brand Brain.
- Upload and organize job photos and videos.
- Generate platform-specific post drafts with AI.
- Review, edit, approve, reject, or revise drafts.
- Schedule approved drafts on a local content calendar.
- Prepare a publish queue for manual export first.
- Track analytics manually or with mock/demo data.
- Manage engagement locally with AI-assisted reply suggestions.
- Learn from approvals, rejections, engagement, and performance over time.

## Core Features

Planned core features:

- Brand Brain for business identity, voice, services, offers, claims, and audience context.
- Media Library for local photos, videos, thumbnails, and metadata.
- AI content generation using a mock provider first.
- Drafts and human approval workflow.
- Local-only calendar scheduling.
- Publish Queue for approved and scheduled content.
- Manual export packages for safe posting outside the app.
- Guarded Facebook Page text or single-image posting for personal local testing after explicit setup.
- Connected Accounts area for future mock and real integration setup.
- Analytics Dashboard for mock, manual, imported, and future platform data.
- Engagement Inbox with local AI reply suggestions.
- AI Memory for learning from user choices and performance.
- Safety Center with emergency pause and kill switch controls.
- Backup, export, and diagnostics tools.

Current completed feature level: local SQLite workflows through Batch 7
recovery plus first-run onboarding/checklist work in Batch 8, with real
publishing and real reply sending intentionally disabled.

## Local-First Privacy Approach

This app is local-first by default. User data should live on the user's machine unless a future feature explicitly requires and documents an external service.

Local-first rules:

- Store app data locally by default.
- Store media files locally by default.
- Use SQLite for MVP data storage.
- Keep real platform integrations disabled until explicitly implemented later.
- Do not scrape social platforms.
- Do not commit local databases, real media, exports, logs, backups, tokens, or secrets.
- Keep mock/demo mode working before adding real providers.
- Keep manual export as the default safe publishing path; any real platform action must stay behind strict safety gates.

## Current Tech Stack

The MVP deliberately uses a small dependency-free local stack:

- Frontend: static HTML, CSS, and JavaScript in `apps/web`.
- Local API: Python standard-library localhost-only bridge in `apps/api`.
- Database services: Python and raw SQLite migrations in `scripts`.

Possible later direction from `AGENTS.md`:

- Frontend: Next.js or another web framework only if the static shell becomes too limiting.
- Desktop: Tauri preferred unless the project later chooses Electron.
- Backend/API: keep the current loopback bridge for MVP; adopt a larger framework only when needed.
- Database: SQLite for MVP.
- ORM: Prisma or Drizzle for TypeScript, or SQLAlchemy/SQLModel for Python.
- Media storage: local filesystem under `data/`.
- AI: mock provider by default, Ollama-compatible local generation behind
  explicit local flags, and OpenAI/Anthropic cloud provider scaffolds for later.
- Jobs: lightweight local job runner first.
- OAuth: server-side only when future integrations are added.
- Token storage: secure local storage/keychain/encryption when available; otherwise `placeholder_not_stored`.

## App Modules

Planned app modules:

- Control Center (`#home`)
- Intro Setup Guide (`#guide`)
- Onboarding
- Brand Brain
- Media Library
- Generate
- Drafts
- Calendar
- Publish Queue
- Manual Export
- Connected Accounts
- Social Integration Setup
- Analytics
- Engagement Inbox
- Weekly Reports
- AI Memory
- Settings
- Safety Center
- Backup & Data
- Diagnostics

Current folders:

```text
apps/
  web/
  desktop/
  api/
packages/
  shared/
  ui/
  types/
  config/
docs/
scripts/
data/
  media/
  exports/
  logs/
```

## Setup Instructions

The web app is currently a static HTML/CSS/JavaScript app. No frontend framework or package manager has been installed yet.

For now:

1. Review `AGENTS.md` before making changes.
2. Copy `.env.example` to `.env` when local server-side configuration is needed.
3. Do not add real secrets to committed files.
4. Follow the batch prompts in order.
5. Run `python -m scripts.local_beta_launcher` for the daily local beta path.
6. Open Control Center at `http://127.0.0.1:8044/#home`.
7. On a fresh database, start with the Onboarding screen and setup checklist.

The localhost server automatically loads a repo-root `.env` file when it
exists. Use `--env-file PATH` only when a different local file is needed.

Opening `apps/web/index.html` directly remains available as a browser-only demo
fallback. See `docs/local-api-bridge.md`.

Python services provide the local SQLite database, scheduling, preflight, job runner, and manual export behavior.

For first-run setup details, see `docs/onboarding.md`.
For emergency pause, kill switch, and Safety Center behavior, see
`docs/safety-controls.md`.
For local backups, exports, and restore preview, see `docs/backup-and-data.md`.
For app health checks and redacted troubleshooting reports, see
`docs/diagnostics.md`.
For desktop packaging readiness, see `docs/desktop-packaging.md`.
For the plain-language user guide, see `docs/user-guide.md`.
For non-coder setup, see `docs/non-coder-setup.md`.
For daily operating steps, see `docs/operator-manual.md`.
For step-by-step workflows, see `docs/common-workflows.md`.
For troubleshooting, see `docs/troubleshooting.md`.
For privacy and local data handling, see `docs/privacy-and-local-data.md`.
For definitions, see `docs/glossary.md`.

## Development Commands

No package manager commands exist yet because there is no `package.json`, `pyproject.toml`, `Makefile`, or equivalent tooling file.

Current direct commands:

```text
python -m scripts.local_beta_launcher
python -m scripts.local_beta_launcher --seed-demo
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
python -m scripts.jobs.local_runner --database data/app.sqlite --once
python -m scripts.jobs.local_runner --database data/app.sqlite --watch --interval-seconds 30
python -m scripts.services.manual_export --database data/app.sqlite --queue-item-id QUEUE_ITEM_ID
python -m scripts.services.analytics --database data/app.sqlite
python -m scripts.services.analytics --database data/app.sqlite --generate-mock
python -m scripts.services.engagement --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care --ingest-mock
python -m scripts.services.ai_memory --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care
python -m scripts.services.weekly_reports --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care --week-start-date 2026-06-08
python -m scripts.services.ai_learning --database data/app.sqlite --brand-profile-id demo-brand-brightside-exterior-care --week-start-date 2026-06-08
python -m scripts.services.diagnostics --database data/app.sqlite --export
python -m scripts.demo_day_check
python -m scripts.launch_check
python -m scripts.desktop.launcher --check
python -m scripts.desktop.launcher --dev
python -m unittest tests.test_integration_flags
python -m unittest tests.test_platform_http_client
python -m unittest tests.test_integration_setup_service
python -m unittest discover tests
python -m compileall -q scripts tests
node --check apps/web/settings.js
node --check apps/web/generate.js
```

Planned command names may include:

```text
npm run dev
npm run build
npm run lint
npm run typecheck
npm run test
npm run db:migrate
npm run db:seed
npm run jobs:once
npm run jobs:dev
npm run launch:check
npm run desktop:dev
npm run desktop:build
```

These commands are examples only until the project tooling is created.
For current desktop readiness, use the Python `scripts.desktop.launcher`
commands above. The npm desktop commands do not exist yet.

## Environment Variables

Use `.env.example` as the committed template. Do not commit `.env`.

Current environment template includes:

```text
APP_ENV=development
LOCAL_DATA_DIR=./data
DATABASE_URL=file:./data/app.sqlite

OPENAI_API_KEY=
ANTHROPIC_API_KEY=

AI_PROVIDER_PREFERENCE=mock
ENABLE_LOCAL_AI_CALLS=false
LOCAL_AI_BASE_URL=http://127.0.0.1:11434
LOCAL_AI_MODEL=llama3.1:8b
LOCAL_AI_TIMEOUT_SECONDS=60

INTEGRATIONS_MODE=mock
ENABLE_REAL_NETWORK_CALLS=false
ENABLE_REAL_OAUTH=false
ENABLE_REAL_PUBLISHING=false
ALLOW_NETWORK_IN_TESTS=false
TOKEN_STORAGE_MODE=placeholder_not_stored

META_CLIENT_ID=
META_CLIENT_SECRET=
META_REDIRECT_URI=
META_GRAPH_API_VERSION=
META_ENABLE_REAL_OAUTH=false
META_ENABLE_REAL_PUBLISHING=false

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=
GOOGLE_ENABLE_REAL_OAUTH=false
GOOGLE_ENABLE_REAL_PUBLISHING=false

TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_REDIRECT_URI=
TIKTOK_ENABLE_REAL_OAUTH=false
TIKTOK_ENABLE_REAL_PUBLISHING=false

LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
LINKEDIN_REDIRECT_URI=
LINKEDIN_ENABLE_REAL_OAUTH=false
LINKEDIN_ENABLE_REAL_PUBLISHING=false

X_CLIENT_ID=
X_CLIENT_SECRET=
X_REDIRECT_URI=
X_ENABLE_REAL_OAUTH=false
X_ENABLE_REAL_PUBLISHING=false
```

Real provider keys and platform credentials are optional future configuration values. They must never be committed.

## Safety Rules

Non-negotiable safety rules:

- No broad real publishing yet. Only guarded Facebook Page text or single-image posting is available for personal local testing after explicit setup.
- No real comment replies or DMs yet.
- No auto-replies.
- No scraping.
- No secrets committed.
- Mock/demo mode first.
- Human approval required before publishing or replying.
- Generated posts must default to review, not automatic approval.
- Scheduling must only allow approved and safe drafts.
- Emergency pause must block scheduling, queue readiness, mock publishing, future real publishing, future real replies, and unsafe automation.
- AI must not invent testimonials, customer names, pricing, availability, certifications, insurance, awards, guarantees, or fake social proof.
- Real platform APIs must come later behind explicit safety gates.

See `docs/safety-and-automation-policy.md` and `AGENTS.md` for the full policy.

## Current Project Status

Current status:

- Repository folder structure exists.
- Placeholder README files exist in empty app, package, script, and local-data folders.
- Starter docs exist for roadmap, safety policy, and database schema planning.
- `.env.example` exists.
- `.gitignore` protects secrets, local databases, local media, exports, logs, build output, dependencies, Python virtual environments, and desktop build artifacts.
- Shared TypeScript product types exist.
- Local SQLite initialization exists.
- Local app settings data layer exists.
- Brand Brain data model and CRUD service exist.
- Local media storage service exists for image/video imports and SQLite metadata.
- Media Library screen supports demo media browsing, filtering, local-only import metadata, and manual metadata editing.
- Safe fake demo seed data exists for dashboards and UI placeholders.
- AI provider abstraction, mock provider, prompt registry, content generation service, Generate screen, draft persistence, Drafts screen, approval workflow, approval queue service, and prompt evaluation fixtures exist.
- Local scheduling models and service exist.
- Calendar screen exists in the static web shell.
- Approved drafts can be scheduled locally through the SQLite-backed browser shell.
- Local job runner exists for due scheduled posts and preflight.
- Publish Queue screen exists in the static web shell.
- Platform requirement matrix and preflight validation service exist.
- Manual export package service exists.
- Local Publish Queue action service exists for marking manually exported and mock-publish transitions.
- Social connector registry, mock OAuth scaffolding, Connected Accounts UI, token safety helpers, Meta connector scaffolds, account-aware preflight, and Social Integration Setup helper exist.
- Integration feature flag validation and a safe server-only platform HTTP client foundation exist for future OAuth/provider work.
- Guarded Meta OAuth token exchange readiness exists behind explicit safety flags and mocked-test coverage; mock mode remains default, and guarded Facebook Page text or single-image posting is the only real publish path.
- Meta account discovery and connector health checks now exist as safe scaffolding with mocked-test coverage; real API discovery is not called by default.
- YouTube connector scaffolding now supports mock OAuth/channel health readiness; video upload and publishing remain disabled.
- TikTok connector scaffolding now supports mock OAuth/profile health readiness; video posting remains disabled.
- LinkedIn connector scaffolding now supports mock OAuth/profile health readiness; text, image, and video publishing remain disabled.
- X connector scaffolding now supports mock OAuth/profile health readiness; text, image, and video publishing remain disabled.
- Batch 7 analytics storage foundation now exists for snapshots, aggregate performance metrics, import audits, explainable content insights, AI memory, and weekly reports.
- Safe fake demo analytics are labeled `mock`; the demo weekly report is labeled `ai_mock`.
- Local analytics service now supports manual snapshots, deterministic mock metrics, latest-snapshot summaries, breakdowns, rankings, import audits, and rule-based insights.
- Analytics Dashboard screen now supports SQLite-backed local summaries, filters, breakdowns, rankings, insight review actions, manual snapshots, and clearly labeled mock metric generation.
- Engagement Inbox database foundation now supports local threads, triage fields, reply-suggestion records, approval audits, import audits, and idempotent fake inbox ingestion. Real comment fetching and reply sending remain disabled.
- Local AI reply suggestions now use Brand Brain context, versioned prompt provenance, deterministic mock generation, local safety review, persisted history, and audit rows. Suggestions remain review-only and are never sent externally.
- Local reply approval workflow now supports editing, local approval, rejection, manual-reply tracking, escalation, spam marking, archive actions, critical-flag blocking, and audit history. Approval never sends a platform reply.
- Engagement Inbox browser screen persists the local reply workflow through the localhost SQLite bridge and keeps a direct-file `localStorage` fallback for static inspection.
- Local AI memory service now promotes explainable analytics insights and local draft/reply review decisions into idempotent evidence-backed memory without storing private engagement text.
- Local weekly report service now upserts one deterministic report per brand and week, preserving mock/manual provenance and labeling mock-only reports as `ai_mock`.
- The localhost Generate screen now runs through the Python content-generation service, loading Brand Brain, selected media metadata, app settings, and bounded active AI-memory summaries from SQLite before the user explicitly saves drafts.
- The Analytics screen now exposes weekly report generation and reviewable AI-memory summaries, including local refresh and archive actions through the SQLite bridge.
- Batch 8 onboarding, Safety Center, Backup & Data, and Diagnostics screens now provide first-run guidance, emergency pause controls, local backup/export, and redacted app health reports.
- Desktop readiness scaffold exists with a Python loopback preview launcher and Tauri-preferred packaging documentation; no production installer exists yet.

Batch 4 docs:

- `docs/scheduling.md`
- `docs/publish-queue.md`
- `docs/local-job-runner.md`
- `docs/manual-export.md`
- `docs/platform-preflight-matrix.md`

Batch 5 setup docs:

- `docs/social-connectors.md`
- `docs/oauth-flow.md`
- `docs/token-security.md`
- `docs/meta-integration.md`
- `docs/facebook-real-use.md`
- `docs/connected-accounts.md`
- `docs/social-integration-setup.md`

Batch 6 integration safety docs:

- `docs/integration-feature-flags.md`
- `docs/platform-http-client.md`
- `docs/meta-oauth-real-mode.md`
- `docs/connector-health-checks.md`
- `docs/youtube-integration.md`
- `docs/tiktok-integration.md`
- `docs/linkedin-integration.md`
- `docs/x-integration.md`
- `docs/integration-security-review.md`

Batch 7 local learning and inbox docs:

- `docs/analytics.md`
- `docs/manual-analytics-entry.md`
- `docs/mock-analytics.md`
- `docs/engagement-inbox.md`
- `docs/reply-suggestions.md`
- `docs/reply-approval-workflow.md`
- `docs/ai-learning-loop.md`
- `docs/weekly-reports.md`
- `docs/batch7-local-workflow.md`

Batch 8 hardening docs:

- `docs/user-guide.md`
- `docs/non-coder-setup.md`
- `docs/operator-manual.md`
- `docs/common-workflows.md`
- `docs/troubleshooting.md`
- `docs/privacy-and-local-data.md`
- `docs/onboarding.md`
- `docs/safety-controls.md`
- `docs/backup-and-data.md`
- `docs/diagnostics.md`
- `docs/desktop-packaging.md`
- `docs/glossary.md`

Not built yet:

- Production desktop installer or native Tauri/Electron wrapper.
- AI media analysis and auto-tagging.
- Broad real social integrations beyond the guarded Facebook path.
- Production-grade token storage for real provider calls.
- Real OAuth/token refresh hardening beyond current guarded Meta readiness.
- Desktop file-picker hardening for packaged-app media import.
- Package-manager based lint/typecheck/build commands.
