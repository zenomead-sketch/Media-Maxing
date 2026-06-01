# Local API Bridge

Run the localhost-only SQLite bridge and static web shell with:

```powershell
python -m apps.api.local_server --database data/app.sqlite --port 8000
```

Open `http://127.0.0.1:8000`.

The bridge delegates browser mutations to the Python SQLite services. It does
not publish posts, send replies, or expose raw token values. See
`docs/local-api-bridge.md`.
