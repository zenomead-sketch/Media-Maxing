# Web App

Static first-pass web app shell.

No frontend framework has been installed yet. Open `index.html` directly in a browser to view the mock dashboard shell.

Available routes:

- `index.html#home`: mock dashboard shell.
- `index.html#brand`: first Brand Brain screen.
- `index.html#settings`: first Settings screen.

Run `python -m apps.api.local_server --database data/app.sqlite --port 8000`
and open `http://127.0.0.1:8000` for the SQLite-backed browser path.

The shell still uses browser adapters for rendering, but `api-client.js`
hydrates them from SQLite and routes supported mutations through the local
bridge. Opening `index.html` directly remains a browser-only `localStorage`
demo fallback. See `docs/local-api-bridge.md`.
