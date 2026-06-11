from __future__ import annotations

import argparse
import json
import os
import webbrowser
from pathlib import Path
from typing import Any

from apps.api.local_server import LocalApiApplication, LocalApiHttpServer
from scripts.db.init_db import REPO_ROOT, resolve_database_path
from scripts.services.local_env import load_local_env_file


APP_NAME = "Local Social AI Manager"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def desktop_readiness_check(
    *,
    database_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict[str, Any]:
    """Return safe desktop packaging readiness metadata without starting a server."""

    resolved_database = resolve_database_path(database_path)
    local_data_dir = os.environ.get("LOCAL_DATA_DIR") or str(REPO_ROOT / "data")
    url = f"http://{host}:{port}"
    return {
        "appName": APP_NAME,
        "status": "ready_for_native_wrapper",
        "packagingDecision": "tauri_preferred_not_installed",
        "host": host,
        "port": port,
        "url": url,
        "databasePath": str(resolved_database),
        "localDataDirectory": local_data_dir,
        "localServerCommand": (
            f"python -m apps.api.local_server --host {host} --port {port}"
        ),
        "desktopDevCommand": f"python -m scripts.desktop.launcher --dev --host {host} --port {port}",
        "desktopCheckCommand": "python -m scripts.desktop.launcher --check",
        "realPublishingEnabled": False,
        "realReplySendingEnabled": False,
        "networkBoundary": "loopback_only",
        "opensRemoteUrls": False,
        "exposesTokensToRenderer": False,
        "packagingNotes": (
            "Tauri is preferred for the future native wrapper, but no Tauri or "
            "Electron dependency is installed yet. This launcher verifies the "
            "existing localhost bridge path without adding native packaging risk."
        ),
    }


def run_desktop_preview(
    *,
    database_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    env_file: str | None = None,
) -> None:
    """Run the localhost app as the desktop dev preview.

    This is intentionally not a native shell. It is the bridge a future Tauri
    wrapper should launch while keeping the app loopback-only.
    """

    if host != DEFAULT_HOST:
        raise ValueError("Desktop preview must bind to 127.0.0.1.")
    load_local_env_file(env_file)
    application = LocalApiApplication(database_path)
    server = LocalApiHttpServer((host, port), application)
    url = f"http://{host}:{port}"
    print(f"{APP_NAME} desktop preview running at {url}")
    print(f"SQLite database: {application.database_path}")
    print("real_publishing=false")
    print("real_reply_sending=false")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Desktop readiness launcher for Local Social AI Manager."
    )
    parser.add_argument("--database", help="Path to the local SQLite database.")
    parser.add_argument("--env-file", help="Optional local .env file to load.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Run the loopback desktop preview server.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print desktop readiness metadata and exit.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the default browser in desktop preview mode.",
    )
    args = parser.parse_args()

    if args.check or not args.dev:
        print(
            json.dumps(
                desktop_readiness_check(
                    database_path=args.database,
                    host=args.host,
                    port=args.port,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return

    run_desktop_preview(
        database_path=args.database,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        env_file=args.env_file,
    )


if __name__ == "__main__":
    main()
