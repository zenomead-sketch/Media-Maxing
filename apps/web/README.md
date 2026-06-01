# Web App

Static local-first web app shell.

No frontend framework has been installed yet. Use the localhost bridge for the
SQLite-backed app. Opening `index.html` directly remains a browser-only demo
fallback.

Available routes:

- `#home`: dashboard shell.
- `#media`: local Media Library.
- `#generate`: offline mock generation and Draft saves.
- `#drafts`: draft approval workflow and scheduling.
- `#calendar`: local scheduling calendar.
- `#queue`: local Publish Queue, preflight, and manual export.
- `#connected`: mock connected accounts.
- `#setup`: social integration setup helper.
- `#engagement`: local Engagement Inbox and reply approvals.
- `#analytics`: manual/mock analytics, weekly reports, and AI memory.
- `#brand`: Brand Brain.
- `#settings`: local app settings and emergency pause.

Run `python -m apps.api.local_server --database data/app.sqlite --port 8000`
and open `http://127.0.0.1:8000` for the SQLite-backed browser path.

The shell uses browser adapters for rendering, while `api-client.js` hydrates
them from SQLite and routes supported mutations through the local bridge.
Opening `index.html` directly uses a `localStorage` demo fallback. See
`docs/local-api-bridge.md`.
