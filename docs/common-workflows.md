# Common Workflows

These are step-by-step paths for normal work. Real publishing is disabled; use
manual export for posting.

## 1. Create a Brand Brain

1. Open Brand Brain or Onboarding.
2. Enter business name, industry, description, services, service areas, voice,
   CTA, website, phone, and email.
3. Save.
4. Review it before generating drafts.

## 2. Upload job photos

1. Open Media Library.
2. Import a supported image or video.
3. Add service tags, location context, notes, and alt text.
4. Keep customer-private information out of notes unless needed.

## 3. Generate post drafts

1. Open Generate.
2. Choose Brand Brain, media, platforms, content goal, and content angle.
3. Add instructions.
4. Generate with mock mode or configured provider.
5. Save selected drafts as `needs_review`.

## 4. Approve a draft

1. Open Drafts.
2. Select a draft.
3. Review content, safety flags, prompt metadata, and media.
4. Edit if needed.
5. Approve only when safe and accurate.

## 5. Schedule a post

1. Open an approved draft.
2. Click Schedule.
3. Select date, time, timezone, and notes.
4. Confirm.
5. Check Calendar and Publish Queue.

## 6. Export a manual posting package

1. Open Publish Queue.
2. Select a ready item.
3. Run preflight if needed.
4. Export the package.
5. Use the local caption, hashtags, media manifest, and posting instructions.

## 7. Mark a post manually exported

1. After you post outside the app, return to Publish Queue.
2. Select the queue item.
3. Mark manually exported.
4. The scheduled post becomes completed locally.

## 8. Enter analytics manually

1. Open Analytics.
2. Use Manual analytics entry.
3. Pick the post, platform, and snapshot date.
4. Enter impressions, views, likes, comments, clicks, leads, and notes.
5. Save.

## 9. Generate mock analytics

1. Open Analytics.
2. Click Generate mock analytics in demo/development mode.
3. Review labels that show `mock`.
4. Do not treat mock data as real results.

## 10. Review content insights

1. Open Analytics.
2. Read content insights.
3. Check evidence and confidence.
4. Apply, dismiss, or archive only if the recommendation makes sense.

## 11. Generate mock engagement

1. Open Engagement Inbox.
2. Click Generate mock engagement.
3. Review source labels that show `mock`.
4. Use it for practice only.

## 12. Generate and approve a reply suggestion

1. Open an engagement item.
2. Click Generate AI Reply.
3. Review the suggested reply, action, confidence, and safety flags.
4. Edit if needed.
5. Approve locally or reject. Approval does not send the reply.

## 13. Create a weekly report

1. Open Analytics.
2. Choose the week.
3. Generate or refresh the weekly report.
4. Read wins, concerns, recommendations, and next-week suggestions.

## 14. Back up app data

1. Open Backup & Data.
2. Choose Full local backup.
3. Include media only if you want copies of media files.
4. Create backup and keep the folder somewhere safe.

## 15. Use emergency pause

1. Open Safety Center.
2. Enable emergency pause.
3. Read what is blocked and what remains allowed.
4. Disable only when you are ready to resume safe local work.

## Start command

Use `python -m apps.api.local_server --database data/app.sqlite --port 8000`
when you want the SQLite-backed app shell.
