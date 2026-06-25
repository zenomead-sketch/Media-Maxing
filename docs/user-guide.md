# User Guide

This guide explains the app in plain language. Real publishing is disabled in
this build. The app helps you prepare, review, schedule, export, and learn from
social content locally.

## What the app does

Local Social AI Manager helps a small business owner turn business information,
job photos, draft ideas, analytics, and engagement into reviewed social media
content. It can generate drafts, save them for approval, schedule approved posts
locally, prepare manual posting packages, track performance, and suggest replies
that still need human review.

## What local-first means

Local-first means your database, media metadata, drafts, schedules, reports, and
exports are stored on your machine by default. The app does not upload your data
to a cloud service by itself. Future real AI or social integrations may send
selected data only when explicitly configured and documented.

## Home screen / Control Center overview

The Home screen is now the Control Center. It is the starting point after setup:
it shows the recommended next step, items that need attention, work that is
ready to do, this week's local schedule signals, and safety status.

Owner Mode is on by default. It keeps the daily workflow visible and folds the
setup/admin areas unless you are actively using them. Turn Owner Mode off only
when you want the app to feel more like a backend dashboard.

Use the **Plug-and-play path** on Control Center when you do not know where to
go next:

1. Add media.
2. Create media post.
3. Approve locally.
4. Post or export from Publish Queue.

The **Facebook posting setup** panel checks the guarded Facebook path through
the local API. It explains whether the local API, Page account, permissions,
token storage, ready queue item, and typed confirmation gate are ready. Token
values are never shown in the browser.

The detailed screens still exist, but they are grouped in the sidebar as Daily
Workflow, Setup, and Advanced Tools so the app feels less crowded. On a fresh
database, start with Onboarding and the setup checklist.

## Intro Setup Guide

Intro Setup Guide is the plain-language walkthrough for first setup. It links to
Onboarding, Brand Brain, Media Library, Connected Accounts, Social Integration
Setup, Drafts, Calendar, Publish Queue, Analytics, Engagement Inbox, Safety
Center, Backup & Data, and Diagnostics.

Use it when you want to set up the app without guessing which screen comes
next. It explains that current social connections are mock/scaffolded, real
OAuth can be configured later, and Manual Export remains the safe posting path.

## Brand Brain

Brand Brain stores your business name, services, service areas, voice, common
CTA, and important rules. AI drafts should use Brand Brain as the source of
truth instead of inventing facts.

## Media Library

Media Library tracks local job photos and videos. It stores metadata such as
tags, service type, location context, and notes. Media files stay local.

For useful generation, add at least 5 real media items for starter mode and aim
for 20 real media items before relying on drafts for serious content planning.
At 50 or more items the app treats the library as strong, and at 100 or more it
has excellent content memory. Generation is not blocked below 20, but the app
will warn that drafts may be less personalized.

A good first 20-item mix is 5 before/after examples, 5 finished job photos, 3
behind-the-scenes photos or videos, 3 team or process shots, 2 customer problem
examples, and 2 seasonal or location-specific examples.

## Generate

Generate creates mock-provider social drafts using Brand Brain, selected media,
platforms, goals, and instructions. Drafts are not published and should be saved
only when you want to review them.

The Generate screen shows a media readiness note. Low media context is guidance,
not a hard stop: you can still create a starter draft, then improve future
drafts by adding more real media.

## Drafts

Drafts is where generated content is reviewed, edited, approved, rejected,
archived, or sent back for revision. Approved drafts can be scheduled. Critical
safety flags must be resolved before scheduling.

## Calendar

Calendar shows locally scheduled posts over time. Scheduling snapshots the
caption, CTA, hashtags, media IDs, and notes so later draft edits do not silently
change already scheduled content.

## Publish Queue

Publish Queue shows waiting, ready, blocked, manually exported, mock published,
failed, canceled, and skipped queue items. It runs preflight checks and shows
blocked reasons. Manual Export is the default safe path.

The only current real posting path is a guarded Facebook Page text or
single-image post. It appears only in Publish Queue, requires a real connected
Facebook Page, required Page permissions, server-side token availability,
passed or warning-only preflight, emergency pause off, and typing
`PUBLISH TO FACEBOOK`. Demo/mock Facebook accounts are blocked from real
posting.

## Manual Export

Manual Export creates a local posting package with caption, hashtags, metadata,
media manifest, and posting instructions. You still post manually in the social
platform app or website.

## Analytics

Analytics shows manual and mock performance data. You can enter metrics by hand,
generate clearly labeled mock analytics for demos, review top and weak posts,
and create simple insights.

## Engagement Inbox

Engagement Inbox tracks mock or manual comments, messages, mentions, reviews,
and leads. AI reply suggestions are local only and require approval. No reply is
sent to a real platform.

## Settings

Settings stores app preferences, local data path information, AI provider mode,
color scheme, and safety defaults. The color scheme picker changes only the
local app appearance; it does not change content, approvals, publishing, or API
settings. Real API keys can be added later in `.env`, not in the UI.

## Safety Center

Safety Center controls emergency pause, automation level, kill switch actions,
pending approvals, safety flags, and audit history. Use it when you want to stop
all risky automation.

## Backup and Data

Backup and Data creates local backups and exports. Backups exclude raw tokens,
API keys, and client secrets by default.

## Diagnostics

Diagnostics checks local data folders, database health, AI mode, integration
status, safety state, queue counts, backups, and recent safe errors. It can
export a redacted diagnostic report.
