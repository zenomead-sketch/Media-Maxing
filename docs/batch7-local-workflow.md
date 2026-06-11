# Batch 7 Local Workflow

Batch 7 keeps the complete review and learning loop on this machine. It does
not fetch live analytics, fetch live comments, publish posts, or send replies.

## Owner Workflow

1. Approve a draft and schedule it locally from Drafts.
2. Run the local job runner so due queue items receive preflight checks.
3. Use a manual export package when you are ready to post outside the app.
4. Record manual analytics in the Analytics screen, or use clearly labeled
   fake demo metrics while exploring the product.
5. Open Engagement and select **Generate mock engagement** to create local
   sample inbox items.
6. Open an item and generate an AI reply suggestion. Review the text and safety
   flags before choosing **Approve Locally**, reject, edit, escalate, archive,
   or mark spam.
7. Open Analytics to refresh AI memory and generate a weekly report.

## What Persists

The localhost bridge stores the workflow in SQLite:

- Draft review history stays in `approval_logs`.
- Manual export readiness and attempts stay in the local publish queue tables.
- Manual analytics use `source = manual`.
- Fake demo analytics use `source = mock`.
- Mock inbox items use `source = mock`.
- Reply suggestions and local decisions stay in `reply_suggestions` and
  `reply_approvals`.
- Evidence-backed learning stays in `ai_memory`.
- Weekly summaries stay in `weekly_reports`.

## Safety Boundary

Approval is a local review decision. No external reply is sent. Marking an item
as manually replied means the owner handled the response outside the app.
Mock analytics are fake data, and manual analytics are owner-entered data.

Use the local app:

```text
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Then open `http://127.0.0.1:8000/#analytics` or
`http://127.0.0.1:8000/#engagement`.

