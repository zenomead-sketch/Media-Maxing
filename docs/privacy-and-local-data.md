# Privacy And Local Data

This app is local-first. Real publishing is disabled, and real platform API
calls are not required by default.

## What data is stored locally

The app can store Brand Brain profiles, settings, media metadata, generated
drafts, scheduled posts, publish queue items, manual export records, analytics,
engagement items, reply suggestions, AI Memory, weekly reports, backups, and
diagnostics.

## Where data is stored

Development data usually lives under `data/`. The SQLite database defaults to
`data/app.sqlite`. Media, exports, backups, diagnostics, and logs also live under
the local data directory.

## What can be backed up

Backups can include app settings, Brand Brain, media metadata, generated posts,
schedules, queue data, analytics, engagement, reply suggestions, AI Memory,
weekly reports, safety reports, and a sanitized database copy.

## What is excluded from backups

Backups exclude raw OAuth tokens, access tokens, refresh tokens, API keys, client
secrets, authorization codes, cache folders, sensitive logs, and provider
responses by default.

## API keys and tokens

API keys and tokens belong in `.env` or future secure storage, never in docs,
screenshots, commits, or frontend responses. Current token storage defaults to
not storing raw tokens.

## What mock data means

Mock data is fake demo data. Mock analytics, mock engagement, mock OAuth, and
mock publishing are for testing local workflows. Do not use them as proof of
real performance or real platform connection.

## AI providers in the future

Future real AI providers may receive selected prompt context such as Brand
Brain, media metadata, draft instructions, or engagement snippets. That should
only happen after provider settings are explicitly configured and documented.

## Customer info

Avoid storing sensitive customer info unless it is needed for the workflow.
Redact private phone numbers, addresses, emails, and names from engagement notes
when possible. Never ask AI to reveal private information.
