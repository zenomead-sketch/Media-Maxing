# Desktop Packaging Readiness

This app is being prepared to run as a local desktop app, but a production
desktop installer is not ready yet.

## Chosen Approach

Tauri is the preferred future wrapper because it is usually lighter than
Electron and fits a local-first app that already has a small web UI. No Tauri or Electron dependency is installed yet because this repository currently has no
JavaScript package manager manifest and the working app is a static web app plus
a Python localhost SQLite bridge.

For this batch, the safest path is a desktop readiness scaffold:

- Keep the existing web app and Python local API bridge working.
- Add a dependency-free desktop preview launcher.
- Document the future native wrapper requirements.
- Avoid adding native packaging dependencies before project tooling is clear.

## Current Desktop Preview

Run a readiness check:

```bash
python -m scripts.desktop.launcher --check
```

Run the desktop preview:

```bash
python -m scripts.desktop.launcher --dev
```

Run the preview without opening a browser automatically:

```bash
python -m scripts.desktop.launcher --dev --no-browser
```

The preview starts the same local web app used during development at:

```text
http://127.0.0.1:8000
```

This is not a packaged native desktop shell yet. It is the local bridge that a
future Tauri wrapper should launch and display.

## Build Command Status

There is no production desktop build command yet. The current build readiness
command is:

```bash
python -m scripts.desktop.launcher --check
```

When Tauri is added later, expected commands can become:

```text
npm run desktop:dev
npm run desktop:build
```

Those npm commands are not real today.

## Local Data Directory

The desktop preview uses the same local data behavior as the web app:

- `LOCAL_DATA_DIR` from `.env` when set.
- `./data` by default during development.
- SQLite database defaults to `data/app.sqlite`.
- Exports, backups, diagnostics, logs, and media remain local.

The local data directory is the user's durable app data home.
Do not store the app data directory in a temporary folder. Back it up through the
Backup & Data screen before destructive changes.

## File Permissions

Future desktop permissions should use least privilege:

- Allow reading/writing only the app data directory by default.
- Use user-selected file picker access for importing media.
- Use a safe command for opening export, backup, and diagnostics folders.
- Do not expose broad filesystem access to the web renderer.
- Do not expose raw tokens, encrypted token blobs, API keys, or OAuth codes.

The current preview does not add native filesystem APIs. It relies on the
localhost bridge and existing server-side services.

## Security Defaults

Real publishing remains disabled. Real reply sending remains disabled. The
desktop preview does not call real social APIs.

Future native wrapper requirements:

- Tauri preferred unless Electron is deliberately chosen later.
- If Electron is used, require `contextIsolation: true`, `nodeIntegration:
  false`, no remote module, no disabled web security, and safe IPC only.
- If Tauri is used, capabilities should be least privilege and scoped to app
  data plus user-selected files.
- Load only local loopback URLs.
- Keep tokens server-side only.
- Redact logs and diagnostic reports.
- Respect emergency pause for scheduling, queue readiness, mock publishing, and
  future real actions.

## Diagnostics And Backups

The Diagnostics screen and CLI are desktop-ready:

```bash
python -m scripts.services.diagnostics --database data/app.sqlite --export
```

The Backup & Data screen and service write local backups under:

```text
data/exports/backups/
```

Future desktop folder buttons should open these folders through a narrow native
command rather than exposing arbitrary shell execution.

## Known Limitations

- No production installer exists yet.
- No Tauri `src-tauri` project exists yet.
- No Electron main/preload process exists.
- No OS signing, notarization, updater, or installer workflow exists.
- No OS keychain integration exists yet.
- Directory selection in onboarding remains a placeholder until native file
  picker support is added.

## Future Tauri Steps

1. Add a package manager manifest only when the repo commits to JS tooling.
2. Create `apps/desktop/src-tauri`.
3. Configure app name and window title as `Local Social AI Manager`.
4. Launch or supervise the Python local API bridge on `127.0.0.1`.
5. Scope filesystem capabilities to app data and user-selected files.
6. Add narrow commands for selecting media, selecting a data directory, and
   opening export/backup folders.
7. Add desktop build checks, installer docs, signing notes, and QA scripts.

Until then, use the Python desktop preview and keep the web app checks passing.
