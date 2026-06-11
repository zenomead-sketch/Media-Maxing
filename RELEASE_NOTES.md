# Release Notes - 0.1.0-local-test

## What This Release Is

This is a local test release of the local-first AI social media manager. It is a working MVP-style handoff for testing safe local workflows with mock/demo data, manual export, and human approval.

It is not production SaaS. Real publishing remains disabled.

## Who it is for

This release is for a non-coder small business owner, local service business, builder, or tester who wants to try the app locally without connecting real social accounts or posting to real platforms.

## What works

- First-run onboarding and setup checklist.
- Brand Brain profile setup.
- Media Library metadata and demo media.
- Mock AI content generation.
- Draft saving, editing, approvals, rejections, revision requests, and archiving.
- Local Calendar scheduling for approved drafts.
- Publish Queue readiness and preflight.
- Manual Export posting packages.
- Connected Accounts mock mode and setup wizard.
- Analytics with manual and mock/demo data.
- Engagement Inbox with mock/manual engagement items.
- AI reply suggestions requiring local approval.
- AI learning loop and weekly reports.
- Safety Center, emergency pause, kill switch actions, and audit logs.
- Backup, restore preview, diagnostics, and launch check script.

## Mock/demo only

- AI content generation uses the mock provider by default.
- Connected Accounts can use mock OAuth.
- Analytics can generate fake demo metrics labeled `mock`.
- Engagement ingestion can generate fake demo comments/messages labeled `mock`.
- Connector health checks are scaffolded or mocked unless future real credentials are configured.

## Local-only

- Scheduling is local-only.
- Publish Queue is local-only.
- Manual Export creates local files only.
- Reply approval is local approval only.
- Backups and diagnostics are written locally.

## Not implemented yet

- Real publishing to social platforms.
- Real reply sending.
- Real platform analytics fetch.
- Real comment/message ingestion.
- Production desktop installer.
- OS-level background scheduling.
- Secure OS keychain token storage for production real OAuth.
- Final verified platform API limits and app review paths.

## How to run it

```powershell
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Open `http://127.0.0.1:8000`.

## How To Test It

```powershell
python -m scripts.launch_check
python -m unittest discover tests
python -m scripts.qa.integration_security_scan .
```

Use `docs/launch-candidate-checklist.md` for the full manual browser QA pass.

## Safety notes

- Real publishing remains disabled.
- Replies are not sent automatically.
- Human approval is required.
- Emergency pause blocks scheduling, queue readiness, mock publishing, future real publishing, future real reply sending, and unsafe automation.
- Manual Export is the safe posting path until a future real-publishing build.

## Backup Notes

Backups are local. Raw OAuth tokens, API keys, client secrets, and encrypted token blobs are excluded by default. Restore is preview-first in the MVP.

## Known risks

- Local scheduling only advances while the app/backend or local runner is running.
- Browser UI still needs full manual QA after automated checks.
- Desktop packaging is not a signed installer yet.
- AI output quality depends on provider, prompts, and Brand Brain quality.
- Platform limits and app review requirements must be verified before real publishing.
