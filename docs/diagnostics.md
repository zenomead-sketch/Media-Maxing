# App Diagnostics

Diagnostics gives a non-coder one place to check whether the local app is healthy enough to keep working.

It is local-only. It does not upload reports, call platform APIs, publish posts, send replies, fetch analytics, or expose tokens.

## What Diagnostics Checks

Diagnostics currently checks:

- App version if available.
- App environment.
- Local data directory path, existence, and writability.
- Media, export, logs, and backup folder availability.
- SQLite database reachability.
- Database migration status.
- AI provider preference and mock AI availability.
- Integration mode and real-publishing disabled policy.
- Connected account counts without token fields.
- Token storage mode.
- Secret exposure safety.
- Emergency pause state.
- Automation level.
- Critical safety flag counts.
- Pending approval counts.
- Local job runner status and last recorded queue attempt.
- Blocked queue count.
- Drafts needing review.
- Engagement items needing reply.
- Analytics data availability.
- Setup checklist status.
- Backup availability.
- Recent safe browser/API errors.

Each result uses one of these statuses:

- `healthy`: no action is needed.
- `warning`: the app can keep running, but the user should review something.
- `error`: a local requirement failed.
- `disabled`: a feature is intentionally off.
- `unknown`: the app cannot check the item in the current mode.

## Diagnostics Screen

Open the app through the local server, then choose **Diagnostics** in the sidebar.

The screen shows:

- Overall health summary.
- Local storage checks.
- Database checks.
- AI checks.
- Social integration checks.
- Safety checks.
- Queue and local job checks.
- Content workflow counts.
- Backup status.
- Recent safe errors.
- What to do next.

Opening `apps/web/index.html` directly still works as a browser-only demo, but filesystem and SQLite checks show as `unknown` or warning because the browser cannot inspect local files.

## Exporting A Report

Click **Export diagnostic report** or run:

```text
python -m scripts.services.diagnostics --database data/app.sqlite --export
```

Reports are written under:

```text
data/exports/diagnostics/diagnostic-report-YYYY-MM-DD-HH-mm.md
```

The report includes:

- Timestamp.
- App environment.
- Local data paths.
- Health results.
- Recent safe errors.
- Setup checklist guidance.
- Safety state.
- Workflow counts.
- Redaction notice.

## What Reports Do Not Include

Diagnostics reports must not include:

- Access tokens.
- Refresh tokens.
- Client secrets.
- Authorization codes.
- Bearer tokens.
- Raw OAuth state values.
- Raw provider payloads.
- Private media contents.
- Full private/customer messages by default.

Recent errors are redacted before they are stored or exported.

## Friendly Error Handling

The web shell records recent browser and API errors in a redacted local list. These errors help troubleshooting, but they are not sent anywhere automatically.

The diagnostics screen can copy a short safe summary or export a local Markdown report. If a check fails, the rest of the diagnostics still run so one broken area does not hide the rest of the app health.

## Limitations

- Diagnostics does not repair data automatically.
- Browser-only mode cannot check real local directories or SQLite health.
- Job runner status is based on local queue attempt records, not a persistent daemon.
- Version metadata is currently unknown until desktop/package metadata is added.
