from __future__ import annotations

import argparse
import json
import os
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from apps.api.local_server import LOOPBACK_HOSTS, LocalApiApplication, LocalApiHttpServer
from scripts.db.init_db import REPO_ROOT, resolve_database_path
from scripts.db.seed_demo import seed_demo_database
from scripts.services.local_env import load_local_env_file


APP_NAME = "Media Maxing"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8044
DEFAULT_ROUTE = "#home"


@dataclass(frozen=True)
class LocalBetaReadiness:
    appName: str
    status: str
    host: str
    port: int
    url: str
    controlCenterUrl: str
    databasePath: str
    localDataDirectory: str
    command: str
    seedDemoCommand: str
    networkBoundary: str
    realPublishingEnabled: bool
    realReplySendingEnabled: bool
    realSocialApisEnabled: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def local_beta_readiness_check(
    *,
    database_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> LocalBetaReadiness:
    _validate_loopback_host(host)
    resolved_database = resolve_database_path(database_path)
    local_data_dir = os.environ.get("LOCAL_DATA_DIR") or str(REPO_ROOT / "data")
    url = f"http://{host}:{port}"
    command_database = f" --database {resolved_database}" if database_path else ""
    return LocalBetaReadiness(
        appName=APP_NAME,
        status="ready_for_local_beta",
        host=host,
        port=port,
        url=url,
        controlCenterUrl=f"{url}/{DEFAULT_ROUTE}",
        databasePath=str(resolved_database),
        localDataDirectory=local_data_dir,
        command=(
            f"python -m scripts.local_beta_launcher{command_database} "
            f"--host {host} --port {port}"
        ),
        seedDemoCommand=(
            f"python -m scripts.local_beta_launcher{command_database} "
            f"--host {host} --port {port} --seed-demo"
        ),
        networkBoundary="loopback_only",
        realPublishingEnabled=False,
        realReplySendingEnabled=False,
        realSocialApisEnabled=False,
        notes=[
            "Starts the local SQLite API and web app together.",
            "Opens Control Center as the daily workflow.",
            "Use --seed-demo only when you want clearly fake demo data.",
            "Real publishing, real replies, and real social APIs remain disabled.",
        ],
    )


def run_local_beta(
    *,
    database_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    open_browser: bool = True,
    env_file: str | None = None,
    seed_demo: bool = False,
) -> None:
    _validate_loopback_host(host)
    load_local_env_file(env_file)
    if seed_demo:
        seed_demo_database(database_path)
    application = LocalApiApplication(database_path)
    server = LocalApiHttpServer((host, port), application)
    readiness = local_beta_readiness_check(
        database_path=application.database_path,
        host=host,
        port=port,
    )
    print(f"{readiness.appName} local beta is running.")
    print(f"Control Center: {readiness.controlCenterUrl}")
    print(f"SQLite database: {application.database_path}")
    print(f"Local data directory: {readiness.localDataDirectory}")
    print("real_publishing=false")
    print("real_reply_sending=false")
    print("real_social_apis=false")
    print("Press Ctrl+C to stop the local app.")
    if open_browser:
        webbrowser.open(readiness.controlCenterUrl)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _validate_loopback_host(host: str) -> None:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("The local beta launcher only binds to a loopback host.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start Media Maxing locally for non-coder beta testing. "
            "This opens Control Center and keeps real publishing/replies disabled."
        )
    )
    parser.add_argument("--database", help="Path to the local SQLite database.")
    parser.add_argument(
        "--env-file",
        help="Optional local .env path. Defaults to the repo-root .env when present.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, choices=sorted(LOOPBACK_HOSTS))
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Seed clearly fake demo data before starting the local app.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening the default browser.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print local beta readiness metadata and exit.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON in --check mode.")
    args = parser.parse_args()

    if args.check:
        readiness = local_beta_readiness_check(
            database_path=args.database,
            host=args.host,
            port=args.port,
        )
        if args.json:
            print(json.dumps(readiness.to_dict(), indent=2, sort_keys=True))
        else:
            print(_human_readiness_report(readiness))
        return 0

    run_local_beta(
        database_path=args.database,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        env_file=args.env_file,
        seed_demo=args.seed_demo,
    )
    return 0


def _human_readiness_report(readiness: LocalBetaReadiness) -> str:
    lines = [
        f"{readiness.appName} local beta status: {readiness.status}",
        f"Control Center: {readiness.controlCenterUrl}",
        f"Database: {readiness.databasePath}",
        f"Local data: {readiness.localDataDirectory}",
        f"Start command: {readiness.command}",
        f"Demo start command: {readiness.seedDemoCommand}",
        "Safety:",
        f"- network_boundary={readiness.networkBoundary}",
        f"- real_publishing={str(readiness.realPublishingEnabled).lower()}",
        f"- real_replies={str(readiness.realReplySendingEnabled).lower()}",
        f"- real_social_apis={str(readiness.realSocialApisEnabled).lower()}",
        "Notes:",
    ]
    lines.extend(f"- {note}" for note in readiness.notes)
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
