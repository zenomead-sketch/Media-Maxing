# Intro Setup Guide

This guide walks a non-coder through the first setup of Media Maxing / Local Social AI Manager.

The app is local-first. Your database, media metadata, drafts, schedules, analytics, engagement items, reports, backups, and diagnostics stay on your machine by default.

Real publishing is disabled in this release. Real replies are not sent. Use mock connections and Manual Export until a future safety-gated real publishing build is implemented.

## 1. Start the App

Run the local database and server:

```text
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Start from **Control Center**. It shows the recommended next step and links to the setup screens.

## 2. Complete Onboarding

Open **Intro Setup Guide** or **Onboarding** from the Setup section.

Onboarding confirms:

- Local data directory.
- Brand Brain basics.
- Default platforms.
- Approval-required safety settings.
- Emergency pause default.
- Optional demo draft.

Nothing is published during onboarding.

## 3. Create Brand Brain

Open **Brand Brain** and add:

- Business name.
- Industry.
- Services.
- Service areas.
- Brand voice.
- Common CTA.
- Website, phone, and email if useful.
- Safety rules and approval rules.

The AI should use Brand Brain as the source of truth. Do not rely on AI to invent services, pricing, guarantees, licensing, testimonials, or availability.

## 4. Upload or Import Media

Open **Media Library**.

Add job photos or videos, then fill in useful metadata:

- Service type.
- Location context.
- Project date.
- Tags.
- Content angle.
- Notes.
- Usage status.

Media should stay local. Avoid uploading private customer information unless the user has permission and a clear reason.

## 5. Choose Social Platforms

Open **Connected Accounts**.

Choose the platforms the business wants to prepare content for:

- Facebook.
- Instagram.
- Threads.
- YouTube Shorts.
- TikTok.
- LinkedIn.
- X.

Use **mock connect** where available. Mock accounts help test the workflow without real credentials, tokens, or platform API calls.

Open **Social Integration Setup** to see what environment variables and developer app setup will be needed later for real OAuth.

Real OAuth and real publishing are still disabled by default.

## 6. Generate Drafts

Open **Generate**.

Choose:

- Brand Brain.
- Media.
- Platforms.
- Content goal.
- Content angle.
- User instructions.

Generate mock drafts, preview them, then save only the drafts you want to review.

Saved drafts start as `needs_review`.

## 7. Review and Approve Drafts

Open **Drafts**.

For each draft:

- Edit fields if needed.
- View safety flags.
- Approve, reject, request revision, or archive.

Approved drafts can be scheduled. Drafts with critical safety flags should not be scheduled.

## 8. Schedule and Export Manually

Open **Calendar** to schedule approved drafts locally.

Open **Publish Queue** to review readiness and preflight warnings.

Use **Manual Export** to create a local posting package. The package helps the user manually copy content into the social platform app or website.

Manual Export does not publish automatically.

## 9. Track Analytics and Engagement

Open **Analytics** to:

- Enter manual metrics.
- Generate clearly labeled mock analytics.
- Review platform/content breakdowns.
- Generate weekly reports.
- Review AI memory.

Open **Engagement Inbox** to:

- Generate mock engagement.
- Track comments/messages locally.
- Generate AI reply suggestions.
- Edit and approve replies locally.

Approved replies are not sent to real platforms.

## 10. Protect the App

Use these screens before serious local testing:

- **Safety Center**: emergency pause, automation level, kill switch actions, safety audit logs.
- **Backup & Data**: local backups, data exports, restore preview.
- **Diagnostics**: local health checks and redacted diagnostic report export.

Backups and diagnostics should not include raw tokens, API keys, client secrets, or OAuth codes by default.

## Safe Operating Rule

For this release:

- Generate drafts locally.
- Approve drafts locally.
- Schedule posts locally.
- Export manual posting packages.
- Track analytics manually or with mock data.
- Review engagement locally.
- Never assume the app posted or replied for you.

Manual Export is the safe path until real publishing is explicitly implemented later.
