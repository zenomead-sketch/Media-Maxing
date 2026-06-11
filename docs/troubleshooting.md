# Troubleshooting

Use Diagnostics first when something feels wrong. Real publishing is disabled,
so troubleshooting should never require posting to a real platform.

## App will not start

Check that you are in the repo folder and run `python -m apps.api.local_server --database data/app.sqlite --port 8000`. If port 8000 is busy, use another port such as `--port 8010`.

## Database error

Run `python -m scripts.db.init_db --database data/app.sqlite`. If the error
continues, create a backup if possible and ask Codex to inspect migrations.

## Missing local data directory

Check Settings or Diagnostics. Create the folder or set `LOCAL_DATA_DIR` in
`.env`. Avoid temporary folders.

## Media upload fails

Check file type, file size, and local data directory writability. Try a small
image first. Do not import private customer material unless needed.

## AI generation fails

Confirm mock mode is enabled. Real provider keys are optional future settings.
If using a real provider later, make sure keys are in `.env`, not committed.

## Mock provider not working

Check Settings and `.env` for safe defaults. Mock mode should not need API keys.
Ask a builder to run tests for the AI provider abstraction.

## Draft will not schedule

The draft must be approved, safe, have usable content, have a valid platform,
have a brand profile, pass media requirements, and emergency pause must be off.

## Queue item is blocked

Open Publish Queue detail and read preflight errors. Common causes are emergency
pause, missing media, critical safety flags, rejected draft status, or missing
required text.

## Manual export fails

Check emergency pause, export folder writability, queue status, and preflight.
Manual export writes local files only.

## Analytics are empty

Add manual analytics or generate mock analytics. Mock analytics is fake demo
data and is labeled `mock`.

## Engagement inbox is empty

Generate mock engagement in demo mode or add/import engagement later. Real
comment fetching is not enabled.

## Connected account setup is missing

Open Social Integration Setup. Mock connect can be used for UI practice. Real
OAuth is not production-ready, and real publishing remains disabled.

## OAuth callback fails

Mock OAuth should work without credentials. Real OAuth requires future setup,
redirect URI configuration, state validation, and safe token handling.

## Emergency pause blocks actions

Open Safety Center. Emergency pause intentionally blocks scheduling, queue
readiness, mock publishing, manual export package creation, and future real
actions.

## Desktop build fails

There is no production desktop build yet. Use `python -m scripts.desktop.launcher --check` for readiness or `python -m scripts.desktop.launcher --dev` for preview.

## How to export diagnostics

Open Diagnostics and export a report, or run `python -m scripts.services.diagnostics --database data/app.sqlite --export`. Reports are local and redacted.
