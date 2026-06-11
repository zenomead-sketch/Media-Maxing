# Operator Manual

This manual is the everyday playbook. Real publishing is disabled, so posting is
done through manual export.

## Daily workflow

1. Open the app with `python -m apps.api.local_server --database data/app.sqlite --port 8000`.
2. Check Safety Center for emergency pause or critical safety flags.
3. Review Drafts that need approval.
4. Check Calendar for upcoming scheduled posts.
5. Check Publish Queue for blocked or ready items.
6. Review Engagement Inbox for needs-reply, urgent, complaint, or lead items.

## Weekly workflow

1. Generate or review content ideas.
2. Approve safe drafts.
3. Schedule posts for the week.
4. Manually export ready posts.
5. Enter analytics for recent posts.
6. Generate weekly reports.
7. Review AI Memory and content insights.
8. Back up app data.

## Monthly workflow

1. Review Brand Brain for outdated services, offers, or service areas.
2. Clean up media metadata.
3. Archive old drafts and resolved engagement items.
4. Review top and underperforming content.
5. Export a full local backup.

## How to review drafts

Open Drafts, filter by `needs_review`, open a draft, read the caption and safety
flags, edit if needed, then approve, reject, request revision, or archive.

## How to schedule posts

Only approved drafts can be scheduled. Open an approved draft, choose Schedule,
pick a future date, time, timezone, and notes, then confirm. Scheduling creates
a Calendar item and Publish Queue item.

## How to manually export posts

Open Publish Queue, select a ready item, run preflight if needed, then create an
export package. Use the package to post manually on the platform. Mark the item
manually exported after you handle it outside the app.

## How to enter analytics

Open Analytics, select Manual analytics entry, choose the post and date, enter
metrics you know, add notes, and save. Manual metrics are marked `manual`.

## How to review engagement

Open Engagement Inbox, filter for urgent, complaints, leads, or needs reply.
Generate a reply suggestion when useful, edit it, approve locally, or mark the
item escalated, spam, ignored, archived, or manually replied.

## How to generate weekly reports

Open Analytics or use the weekly report service for the brand and week. Reports
summarize wins, concerns, recommendations, top posts, weak posts, engagement,
and learning updates.

## How to back up data

Open Backup & Data and create a full local backup. Raw tokens and secrets are
excluded by default. Back up before major changes.

## How to use emergency pause

Open Safety Center and enable emergency pause if you want to stop scheduling,
queue readiness, mock publishing, manual export package creation, and future
real actions. You can still view data, edit drafts, read analytics, and create
backups.
