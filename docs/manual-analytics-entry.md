# Manual Analytics Entry

Manual analytics let you record performance after checking a social platform
yourself. This is the safest way to track real results before platform
analytics integrations exist.

## Add A Snapshot

1. Start the local app and open **Analytics**.
2. Find **Manual analytics entry**.
3. Select the post you checked.
4. Choose the platform and snapshot date.
5. Enter the metrics you can see.
6. Add an optional note.
7. Select **Save manual snapshot**.

Every manually entered row is stored locally with:

```text
source = manual
```

The app does not fetch analytics from the platform when you save the form.

## Metrics

- **Impressions:** times the post was shown.
- **Reach:** accounts or people reached when the platform provides it.
- **Views:** video or content views.
- **Likes:** likes or reactions.
- **Comments:** comments visible on the post.
- **Shares:** shares or repost-like actions.
- **Saves:** saves or bookmarks when available.
- **Clicks:** clicks attributed to the post when available.
- **Leads:** estimate requests or other lead signals you choose to track.
- **Messages:** inbound message signals you choose to track.
- **Calls:** phone-call lead signals you choose to track.
- **Website clicks:** visits to the business website attributed to the post.

Platforms define metrics differently. Enter only values you can verify. Use
notes when a platform label needs clarification.

## Avoid Duplicate Snapshots

Snapshots are point-in-time measurements. When you check the same post again,
use a new date. The app prevents a duplicate snapshot with the same source,
post links, platform, and snapshot date.

If you need to correct an existing snapshot, update the saved row through the
local service instead of creating a duplicate.

## Why Manual Data Matters

Manual entries stay visibly separate from fake demo data. Reports and learning
memory can use them as local evidence, but low-volume patterns remain
low-confidence ideas to test. They are not guarantees.

## Privacy And Safety

- Data stays in the local SQLite database.
- No analytics API is called.
- Do not paste tokens, passwords, or private customer information into notes.
- Manual analytics do not publish posts or send replies.
