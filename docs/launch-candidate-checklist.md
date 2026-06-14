# Launch Candidate Checklist

This checklist is for local launch testing. It does not mean the app is production SaaS, and it does not enable real publishing, real reply sending, or real platform analytics.

Use the automated launch check first:

```powershell
python -m scripts.launch_check
```

Run the demo-day walkthrough after that:

```powershell
python -m scripts.demo_day_check
```

For a faster script smoke check that skips the full test suite:

```powershell
python -m scripts.launch_check --skip-tests
```

The launch check creates a throwaway local database if you pass `--database`, seeds demo data, runs local-only workflow checks, creates backup and diagnostic artifacts, and runs a redacted security scan. The demo-day check walks the practical user flow from onboarding through diagnostics. Neither script calls real APIs.

## Launch Candidate Decision

- **Pass**: All checks pass and there are no secret findings. Safe to test locally with mock/manual workflows.
- **Partial**: Core safety and local workflows pass, but a non-blocking item is still documented, such as no production desktop installer.
- **Fail**: A workflow, safety gate, security scan, or test command fails. Do not treat the app as a launch candidate until fixed.

Real publishing remains disabled by default in all launch-candidate states. Guarded Facebook Page text or single-image posting is allowed only when explicitly configured and confirmed.

## Install and Setup

- Confirm Python is installed.
- Confirm `python -m unittest discover tests` can run.
- Confirm there is no required package install step for the static web MVP.
- Confirm the user can start the app with `start-media-maxing.bat`.
- Confirm the terminal fallback works: `python -m scripts.local_beta_launcher`.
- Confirm Control Center opens at `http://127.0.0.1:8044/#home`.

## Environment Variables

- Confirm `.env.example` exists.
- Confirm default integration mode is mock or disabled.
- Confirm `ENABLE_REAL_PUBLISHING=false`.
- Confirm API keys and client secrets are blank in examples.
- Do not call real APIs during launch QA.

## Database and Seed

Automated:

```powershell
python -m scripts.db.init_db --database data/launch-check/launch.sqlite
python -m scripts.db.seed_demo --database data/launch-check/launch.sqlite
```

Expected:

- Migrations apply cleanly.
- Demo Brand Brain exists.
- Demo media exists.
- Demo generated posts exist.
- Demo scheduled posts and Publish Queue items exist.
- Approval logs exist.

## Core Workflow Test

Run the local-first workflow without touching real APIs:

1. Start from a clean database.
2. Complete onboarding.
3. Create Brand Brain.
4. Add or seed media.
5. Generate mock content.
6. Save to Drafts.
7. Approve draft.
8. Schedule draft.
9. Run local job runner.
10. View Publish Queue.
11. Run preflight.
12. Export Manual Export posting package.
13. Mark manually exported.
14. Enter manual analytics.
15. Generate mock engagement.
16. Generate reply suggestion.
17. Approve reply locally.
18. Generate AI memory.
19. Generate weekly report.
20. Create backup.
21. Export diagnostics.

The automated `scripts.demo_day_check` script covers this workflow as a deterministic local walkthrough. Browser steps still need a manual pass before calling the app launch-candidate ready.

## Onboarding

Manual browser check:

- Open `#onboarding`.
- Confirm Welcome explains local-first behavior.
- Confirm local data directory status is visible.
- Create or confirm a Brand Brain profile.
- Confirm safety settings default to approval required.
- Skip media or import demo media.
- Complete onboarding or skip with confirmation.
- Refresh and confirm state persists.

## Brand Brain

- Confirm Brand Brain screen loads.
- Confirm business name, industry, services, service areas, voice, CTA, and contact fields are visible.
- Confirm save feedback appears.
- Confirm empty state is understandable on a fresh database.

## Media Library

- Confirm Media Library screen loads.
- Confirm seeded demo media is visible.
- Confirm local/mock labels are clear.
- Confirm missing local files do not crash the UI.
- Confirm import/upload controls are clearly local.

## Generate

- Confirm Generate screen loads.
- Confirm mock provider is available by default.
- Generate mock content.
- Confirm generated output is structured by platform.
- Confirm safety flags and prompt metadata are visible.
- Save selected output to Drafts.

## Drafts and Approvals

- Confirm Drafts list loads.
- Filter by platform and approval status.
- Open draft detail.
- Edit draft fields.
- Approve one draft locally.
- Reject or request revision on another draft.
- Confirm approval logs are stored.
- Confirm approved edits require review again.

## Calendar

- Schedule an approved draft.
- Confirm the scheduled post appears in Calendar.
- Confirm reschedule persists.
- Confirm cancel changes local state and does not delete records.
- Confirm unapproved drafts cannot be scheduled.

## Publish Queue

- Run local jobs:

```powershell
python -m scripts.jobs.local_runner --database data/launch-check/launch.sqlite --once
```

- Open Publish Queue.
- Confirm waiting, ready, blocked, manual export, and mock publish labels are clear.
- Run preflight locally.
- Confirm blocked reasons are visible.
- Confirm real publishing disabled message is visible.

## Manual Export

- Export an eligible queue item.
- Confirm the package includes `caption.txt`, `post.md`, `metadata.json`, `media-manifest.json`, and `posting-instructions.md`.
- Confirm Manual Export is clearly labeled as not an automatic publish.
- Mark the item manually exported only after user confirmation.
- Confirm exports contain no tokens or secrets.

## Connected Accounts Mock Mode

- Open Connected Accounts.
- Mock connect Instagram or Facebook.
- Confirm account appears as mock/demo.
- Disconnect locally.
- Confirm tokens are never shown.
- Confirm broad real publishing remains disabled and Facebook text publishing remains locked unless explicitly configured.

## Setup Wizard

- Open Social Integration Setup.
- Confirm all platforms are listed.
- Confirm missing credentials are shown without showing secrets.
- Confirm mock mode and real mode are explained.
- Confirm publishing disabled warnings are visible.

## Analytics

- Generate mock analytics.
- Add one manual analytics snapshot.
- Confirm mock data is labeled mock.
- Confirm manual data is labeled manual.
- Confirm summary cards, platform breakdown, content goal breakdown, content angle breakdown, top posts, and weak posts render.

## Engagement Inbox

- Generate mock engagement.
- Filter by status, sentiment, intent, priority, and source.
- Open detail panel.
- Mark one item ignored.
- Mark one item escalated.
- Mark one item replied manually.
- Confirm replies are not sent automatically.

## Reply Suggestions

- Generate an AI reply suggestion with the mock provider.
- Confirm the suggestion requires local approval.
- Approve a safe suggestion locally.
- Reject or edit another suggestion.
- Confirm spam recommends ignore or mark spam.
- Confirm critical safety flags block approval.

## AI Learning Loop

- Generate mock analytics and engagement.
- Run learning memory update.
- Confirm evidence-backed memory is created.
- Confirm low-confidence findings are labeled honestly when data is weak.
- Confirm memory is not deleted automatically.

## Weekly Reports

- Generate a weekly report.
- Confirm it includes wins, concerns, recommendations, top posts, platform breakdown, engagement summary, lead signals, and next-week suggestions.
- Confirm recommendations do not overstate weak data.

## Safety Center

- Open Safety Center.
- Confirm emergency pause, automation level, publishing safety, reply safety, queue status, connected account safety, critical flags, pending approvals, kill switch actions, and audit log are visible.
- Confirm dangerous actions require confirmation.

## Emergency pause

## Safety Workflow Test

1. Enable emergency pause.
2. Confirm scheduling is blocked.
3. Confirm queue readiness is blocked or moved to a safe blocked/paused state.
4. Confirm mock publishing is blocked.
5. Confirm broad real publishing remains disabled and Facebook text publishing remains locked unless explicitly configured.
6. Confirm reply sending is unavailable.
7. Confirm Manual Export behavior matches policy; the MVP blocks manual export while paused.
8. Confirm safety audit logs are created.
9. Disable emergency pause.
10. Confirm safe local actions resume.

## Backup and Restore Preview

- Create a full local backup without media.
- Confirm `backup-manifest.json` exists.
- Confirm raw tokens and secrets are excluded by default.
- Run restore preview on the backup.
- Confirm invalid backups are rejected safely.
- Do not overwrite current user data without a pre-restore backup and explicit confirmation.

## Diagnostics

- Open Diagnostics.
- Confirm local storage, database, AI, integrations, safety, queue/jobs, workflow, backups, and recent errors sections appear.
- Export diagnostic report.
- Confirm the report is local and redacted.

## Desktop Packaging

- Review `docs/desktop-packaging.md`.
- Confirm desktop readiness is documented.
- Confirm no production installer is claimed unless a real desktop build exists.
- Confirm desktop renderer must not receive tokens or secrets.

## Documentation

- Review README and user-facing docs.
- Confirm a non-coder can find setup, local server, backup, diagnostics, manual export, and safety instructions.
- Confirm unfinished features are described honestly.

## Security Scan

Run:

```powershell
python -m scripts.qa.integration_security_scan . data/exports data/launch-check
```

Search terms include:

- `access_token`
- `refresh_token`
- `client_secret`
- `Authorization`
- `Bearer`
- `id_token`
- `appsecret_proof`
- `signed_request`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `META_CLIENT_SECRET`
- `GOOGLE_CLIENT_SECRET`
- `TIKTOK_CLIENT_SECRET`
- `LINKEDIN_CLIENT_SECRET`
- `X_CLIENT_SECRET`

It is okay for docs and `.env.example` to mention variable names. It is not okay for real secret-looking values to appear.

Secret exposure checks:

- Frontend-safe config contains no secrets.
- SafeSocialAccountDTO contains no tokens.
- Backups exclude raw tokens by default.
- Diagnostic reports exclude secrets.
- Logs redact tokens.
- Error messages redact tokens.
- Manual Export packages contain no tokens.
- Test snapshots contain no secrets.

## Build Checks

Run all available checks:

```powershell
python -m unittest discover tests
python -m compileall -q scripts tests apps\api
node --check apps\web\settings.js
node --check apps\web\generate.js
node --check apps\web\analytics.js
node --check apps\web\engagement.js
node --check apps\web\api-client.js
```

There is no `package.json` build command in the static web MVP. Treat build status as partial until a package/build tool or desktop installer is added.

## Final Build

- Confirm available checks pass.
- Confirm no real APIs are called.
- Confirm no real publishing or reply sending is enabled.
- Confirm launch status is pass or partial with documented limitations.
- If any launch check fails, fix the smallest safe blocker before local testing.
