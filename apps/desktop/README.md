# Desktop App

Desktop readiness scaffold for Local Social AI Manager.

The repo does not currently include Tauri, Electron, Node package scripts, or a
production installer. The safe desktop path for now is a dependency-free Python
preview launcher around the existing localhost SQLite bridge.

Run a readiness check:

```bash
python -m scripts.desktop.launcher --check
```

Run the desktop preview:

```bash
python -m scripts.desktop.launcher --dev
```

This starts the local app at `http://127.0.0.1:8000`. It does not publish, send
replies, call real social APIs, or expose tokens to the renderer.

Tauri is the preferred future wrapper once the repo has clear package tooling.
See `docs/desktop-packaging.md` for the packaging plan, security boundaries,
known limitations, and future native steps.
