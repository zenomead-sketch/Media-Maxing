# Local Reply Approval Workflow

The Engagement Inbox reply approval workflow is local-only. Approving a reply means the owner reviewed the draft. It does not send a reply to Facebook, Instagram, Threads, or any other platform.

## Workflow

1. Open an Engagement Inbox item.
2. Generate a local AI-assisted reply suggestion.
3. Review the suggested text, tone, recommended action, reason summary, and safety flags.
4. Edit the suggestion if needed.
5. Approve locally, reject it, escalate the item, mark it as spam, archive it, or record that the owner replied manually outside the app.

Every action creates a `reply_approvals` audit row.

## Safety Blocking

Critical safety flags block local approval until the reply is edited and the final outbound text passes the local reviewer.

Blocked approval shows:

```text
This suggestion has critical safety flags. Edit it before approving.
```

Spam approval shows:

```text
This item is marked spam. Reply approval is not recommended.
```

Critical flags include invented pricing, invented availability, unsupported guarantees, aggressive language, privacy risk, complaint mishandling, and approval-bypass language.

## Local Statuses

- `reply_suggested`: a draft exists for owner review.
- `reply_approved`: the owner approved the wording locally.
- `replied_manually`: the owner handled the reply outside the app.
- `escalated`: the item needs direct owner attention.
- `spam`: the item should not receive a reply.
- `archived`: the local record remains stored but is no longer active.

## Browser Demo

The static Engagement Inbox mirrors this workflow. Through the localhost
bridge, actions persist to SQLite. Direct-file mode remains a `localStorage`
demo fallback. Data stays on the current device and mock/manual provenance
remains visible.

## Limits

- There is no external reply-send method.
- No social platform API is called.
- Approval is never automatic.
- Raw provider payloads are not shown in the browser.
