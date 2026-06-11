from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sqlite3
import sys
import uuid
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings
from scripts.services.safety_center import SafetyCenterService


REPO_ROOT = Path(__file__).resolve().parents[2]

BACKUP_TYPES = {
    "full_local_backup",
    "database_only",
    "content_only",
    "brand_brain_export",
    "media_metadata_export",
    "analytics_export",
    "engagement_export",
    "ai_memory_export",
    "safety_report_export",
}

SENSITIVE_COLUMNS = {
    "encrypted_access_token",
    "encrypted_refresh_token",
    "access_token",
    "refresh_token",
    "authorization_code",
    "client_secret",
    "api_key",
    "bearer_token",
}

SENSITIVE_KEY_PATTERN = re.compile(
    r"(access[_-]?token|refresh[_-]?token|client[_-]?secret|api[_-]?key|authorization|bearer|id[_-]?token|authorization[_-]?code)",
    re.IGNORECASE,
)

JSON_EXPORTS: dict[str, dict[str, list[str]]] = {
    "app-settings.json": {"tables": ["app_settings", "users", "onboarding_state"]},
    "brand-profiles.json": {"tables": ["brand_profiles"]},
    "media-assets.json": {"tables": ["media_assets"]},
    "generated-posts.json": {"tables": ["generated_posts", "approval_logs"]},
    "scheduled-posts.json": {"tables": ["scheduled_posts"]},
    "publish-queue.json": {
        "tables": ["publish_queue_items", "publish_attempts", "published_posts"]
    },
    "analytics.json": {
        "tables": [
            "analytics_snapshots",
            "post_performance_metrics",
            "analytics_imports",
            "content_insights",
        ]
    },
    "engagement.json": {
        "tables": [
            "engagement_threads",
            "engagement_items",
            "reply_suggestions",
            "reply_approvals",
            "engagement_imports",
        ]
    },
    "ai-memory.json": {"tables": ["ai_memory"]},
    "weekly-reports.json": {"tables": ["weekly_reports"]},
    "connected-accounts.json": {
        "tables": [
            "social_accounts",
            "connector_audit_logs",
            "connector_health_checks",
        ]
    },
}

CATEGORY_FILES = {
    "full_local_backup": list(JSON_EXPORTS) + ["safety-report.json"],
    "database_only": [],
    "content_only": [
        "brand-profiles.json",
        "media-assets.json",
        "generated-posts.json",
        "scheduled-posts.json",
        "publish-queue.json",
        "weekly-reports.json",
    ],
    "brand_brain_export": ["brand-profiles.json"],
    "media_metadata_export": ["media-assets.json"],
    "analytics_export": ["analytics.json"],
    "engagement_export": ["engagement.json"],
    "ai_memory_export": ["ai-memory.json"],
    "safety_report_export": ["safety-report.json"],
}

TYPES_WITH_DATABASE_COPY = {"full_local_backup", "database_only"}


class BackupServiceError(RuntimeError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class BackupManifest:
    backupId: str
    createdAt: str
    appVersion: str | None
    backupType: str
    includeMedia: bool
    includeSensitiveTokens: bool
    includeTokenMetadata: bool
    tableCounts: dict[str, int]
    fileCounts: dict[str, int]
    checksumPlaceholders: dict[str, str]
    warnings: list[str]
    restoreNotes: list[str]
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backupId": self.backupId,
            "createdAt": self.createdAt,
            "appVersion": self.appVersion,
            "backupType": self.backupType,
            "includeMedia": self.includeMedia,
            "includeSensitiveTokens": self.includeSensitiveTokens,
            "includeTokenMetadata": self.includeTokenMetadata,
            "tableCounts": self.tableCounts,
            "fileCounts": self.fileCounts,
            "checksumPlaceholders": self.checksumPlaceholders,
            "warnings": self.warnings,
            "restoreNotes": self.restoreNotes,
            "files": self.files,
        }


class BackupService:
    """Local backup/export service with token-safe defaults.

    The service writes local files only. It never uploads backups and never
    includes raw token columns in structured exports.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def create_backup(
        self,
        *,
        backup_type: str = "full_local_backup",
        backup_name: str | None = None,
        include_media: bool = False,
        include_token_metadata: bool = False,
        include_sensitive_tokens: bool = False,
    ) -> dict[str, Any]:
        if backup_type not in BACKUP_TYPES:
            raise BackupServiceError(
                f"Unsupported backup type: {backup_type}",
                ["unsupported_backup_type"],
            )
        if include_sensitive_tokens:
            raise BackupServiceError(
                "Raw tokens are not supported in MVP backups.",
                ["sensitive_token_backup_blocked"],
            )

        created_at = _utc_now()
        backup_id = f"backup-{uuid.uuid4()}"
        backup_path = self._backup_path(created_at, backup_name or backup_type)
        backup_path.mkdir(parents=True, exist_ok=False)

        table_counts = self._table_counts()
        warnings = [
            "Raw OAuth tokens, encrypted token blobs, API keys, and client secrets are excluded.",
            "Restore is preview-first in the MVP; review the plan before overwriting local data.",
        ]
        restore_notes = [
            "Read backup-manifest.json before restoring.",
            "Create a fresh pre-restore backup before any destructive restore.",
            "Tokens are not restored by default.",
        ]
        files_written: list[str] = []
        file_counts = {
            "jsonFiles": 0,
            "csvFiles": 0,
            "markdownFiles": 0,
            "mediaCopied": 0,
            "mediaMissing": 0,
            "databaseFiles": 0,
        }

        for file_name in CATEGORY_FILES[backup_type]:
            if file_name == "safety-report.json":
                self._write_safety_report(backup_path / file_name)
            else:
                self._write_json_export(
                    backup_path / file_name,
                    JSON_EXPORTS[file_name]["tables"],
                    include_token_metadata=include_token_metadata,
                )
            files_written.append(file_name)
            file_counts["jsonFiles"] += 1

        if backup_type == "analytics_export":
            self._write_analytics_csv(backup_path / "analytics.csv")
            files_written.append("analytics.csv")
            file_counts["csvFiles"] += 1

        if backup_type == "safety_report_export":
            self._write_safety_report_markdown(backup_path / "safety-report.md")
            files_written.append("safety-report.md")
            file_counts["markdownFiles"] += 1

        if backup_type in TYPES_WITH_DATABASE_COPY:
            self._copy_sanitized_database(backup_path / "database-backup.sqlite")
            files_written.append("database-backup.sqlite")
            file_counts["databaseFiles"] += 1

        if include_media:
            media_result = self._copy_media_files(backup_path)
            file_counts["mediaCopied"] = media_result["copied"]
            file_counts["mediaMissing"] = media_result["missing"]
            if media_result["missing"]:
                warnings.append(
                    f"{media_result['missing']} linked media file(s) were missing and could not be copied."
                )
        elif backup_type == "full_local_backup":
            warnings.append("Media files were not copied. Media metadata was exported.")

        manifest = BackupManifest(
            backupId=backup_id,
            createdAt=created_at,
            appVersion=None,
            backupType=backup_type,
            includeMedia=include_media,
            includeSensitiveTokens=False,
            includeTokenMetadata=include_token_metadata,
            tableCounts=table_counts,
            fileCounts=file_counts,
            checksumPlaceholders={
                "status": "not_implemented",
                "note": "Checksums are planned for a later backup hardening pass.",
            },
            warnings=warnings,
            restoreNotes=restore_notes,
            files=sorted(files_written),
        )
        (backup_path / "backup-manifest.json").write_text(
            _pretty_json(manifest.to_dict()),
            encoding="utf-8",
        )
        self._write_readme(backup_path / "README.md", manifest)

        return {
            **manifest.to_dict(),
            "backupPath": str(backup_path),
            "localOnly": True,
            "realPublishing": False,
            "realReplySending": False,
        }

    def list_backups(self) -> list[dict[str, Any]]:
        backup_root = self._backup_root()
        if not backup_root.exists():
            return []
        items: list[dict[str, Any]] = []
        for manifest_path in backup_root.glob("*/backup-manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            manifest["backupPath"] = str(manifest_path.parent)
            items.append(manifest)
        return sorted(items, key=lambda item: item.get("createdAt", ""), reverse=True)

    def preview_restore(self, backup_path: str | Path) -> dict[str, Any]:
        path = Path(backup_path).expanduser()
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        manifest_path = path / "backup-manifest.json"
        if not manifest_path.exists():
            raise BackupServiceError(
                "Backup manifest is missing.",
                ["manifest_missing"],
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise BackupServiceError(
                "Backup manifest could not be parsed.",
                ["manifest_invalid_json"],
            ) from error

        missing_files = [
            file_name
            for file_name in manifest.get("files", [])
            if file_name != "database-backup.sqlite"
            and not (path / str(file_name)).exists()
        ]
        if "database-backup.sqlite" in manifest.get("files", []) and not (
            path / "database-backup.sqlite"
        ).exists():
            missing_files.append("database-backup.sqlite")
        if missing_files:
            raise BackupServiceError(
                "Backup files are missing.",
                ["backup_files_missing"],
            )

        return {
            "status": "ready",
            "backupPath": str(path),
            "backupId": manifest.get("backupId"),
            "backupType": manifest.get("backupType"),
            "createdAt": manifest.get("createdAt"),
            "includeMedia": bool(manifest.get("includeMedia")),
            "willRestoreTokens": False,
            "requiresConfirmation": True,
            "destructiveRestoreImplemented": False,
            "preRestoreBackupRequired": True,
            "files": manifest.get("files", []),
            "tableCounts": manifest.get("tableCounts", {}),
            "warnings": [
                *manifest.get("warnings", []),
                "Actual destructive restore is not automatic in this MVP screen.",
            ],
            "restorePlan": [
                "Validate backup manifest and expected files.",
                "Create a new pre-restore backup before any overwrite.",
                "Restore selected JSON/database data only after explicit confirmation.",
                "Do not restore tokens by default.",
            ],
        }

    def _backup_root(self) -> Path:
        settings = load_app_settings(self.database_path)
        data_dir = Path(settings.localDataDirectory).expanduser()
        if not data_dir.is_absolute():
            data_dir = (REPO_ROOT / data_dir).resolve()
        return data_dir / "exports" / "backups"

    def _backup_path(self, created_at: str, backup_name: str) -> Path:
        timestamp = created_at.replace(":", "-").replace("T", "-").replace("Z", "")
        timestamp = timestamp[:16]
        slug = _slugify(backup_name)
        base = self._backup_root() / f"{timestamp}-{slug}"
        if not base.exists():
            return base
        return self._backup_root() / f"{timestamp}-{slug}-{uuid.uuid4().hex[:8]}"

    def _table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with closing(sqlite3.connect(self.database_path)) as connection:
            for table in self._table_names(connection):
                counts[table] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
        return counts

    def _write_json_export(
        self,
        path: Path,
        tables: list[str],
        *,
        include_token_metadata: bool,
    ) -> None:
        payload = {
            "exportedAt": _utc_now(),
            "localOnly": True,
            "includeSensitiveTokens": False,
            "tables": {},
        }
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            existing = set(self._table_names(connection))
            for table in tables:
                if table == "platform_tokens" and not include_token_metadata:
                    continue
                if table not in existing:
                    payload["tables"][table] = []
                    continue
                rows = connection.execute(f"SELECT * FROM {table}").fetchall()
                payload["tables"][table] = [
                    self._sanitize_row(table, dict(row)) for row in rows
                ]
        path.write_text(_pretty_json(payload), encoding="utf-8")

    def _write_safety_report(self, path: Path) -> None:
        payload = {
            "exportedAt": _utc_now(),
            "localOnly": True,
            "includeSensitiveTokens": False,
            "safetyCenter": SafetyCenterService(self.database_path).get_state(),
        }
        path.write_text(_pretty_json(_redact_sensitive(payload)), encoding="utf-8")

    def _write_safety_report_markdown(self, path: Path) -> None:
        state = SafetyCenterService(self.database_path).get_state()
        lines = [
            "# Safety Report",
            "",
            f"Exported at: {_utc_now()}",
            "",
            "This report is local only. It does not include tokens or secrets.",
            "",
            f"Emergency pause: {state['emergencyPause']['enabled']}",
            f"Automation level: {state['automationLevel']}",
            f"Real publishing: {state['publishingSafety']['status']}",
            f"Reply safety: {state['replySafety']['status']}",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_analytics_csv(self, path: Path) -> None:
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            if "analytics_snapshots" not in self._table_names(connection):
                path.write_text("", encoding="utf-8")
                return
            rows = connection.execute("SELECT * FROM analytics_snapshots").fetchall()
        with path.open("w", newline="", encoding="utf-8") as handle:
            if not rows:
                handle.write("")
                return
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(self._sanitize_row("analytics_snapshots", dict(row)))

    def _copy_sanitized_database(self, destination: Path) -> None:
        shutil.copy2(self.database_path, destination)
        with closing(sqlite3.connect(destination)) as connection:
            connection.execute("PRAGMA foreign_keys = OFF")
            tables = set(self._table_names(connection))
            if "platform_tokens" in tables:
                columns = set(self._columns(connection, "platform_tokens"))
                updates = []
                if "encrypted_access_token" in columns:
                    updates.append("encrypted_access_token = NULL")
                if "encrypted_refresh_token" in columns:
                    updates.append("encrypted_refresh_token = NULL")
                if updates:
                    connection.execute(f"UPDATE platform_tokens SET {', '.join(updates)}")
            connection.commit()

    def _copy_media_files(self, backup_path: Path) -> dict[str, int]:
        copied = 0
        missing = 0
        media_root = backup_path / "media"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.row_factory = sqlite3.Row
            if "media_assets" not in self._table_names(connection):
                return {"copied": 0, "missing": 0}
            rows = connection.execute("SELECT * FROM media_assets").fetchall()
        for row in rows:
            row_dict = dict(row)
            for column in ("original_path", "processed_path", "thumbnail_path"):
                raw_path = row_dict.get(column)
                if not raw_path:
                    continue
                source = self._resolve_media_path(str(raw_path))
                if not source.exists() or not source.is_file():
                    missing += 1
                    continue
                target_dir = media_root / str(row_dict.get("id", "unknown"))
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target_dir / source.name)
                copied += 1
        return {"copied": copied, "missing": missing}

    def _resolve_media_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        settings = load_app_settings(self.database_path)
        data_dir = Path(settings.localDataDirectory).expanduser()
        candidates = []
        if data_dir.is_absolute():
            candidates.append(data_dir / path)
        else:
            candidates.append((REPO_ROOT / data_dir / path).resolve())
        candidates.append((REPO_ROOT / path).resolve())
        return next((candidate for candidate in candidates if candidate.exists()), candidates[-1])

    def _write_readme(self, path: Path, manifest: BackupManifest) -> None:
        lines = [
            "# Local Backup",
            "",
            f"Backup ID: `{manifest.backupId}`",
            f"Created: `{manifest.createdAt}`",
            f"Type: `{manifest.backupType}`",
            "",
            "This backup was created locally. It was not uploaded anywhere.",
            "",
            "Raw OAuth tokens, API keys, client secrets, authorization codes, and encrypted token blobs are excluded by default.",
            "",
            "Use the Backup & Data screen to preview restore contents before overwriting local data.",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _sanitize_row(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        sanitized = {}
        for key, value in row.items():
            if key in SENSITIVE_COLUMNS or SENSITIVE_KEY_PATTERN.search(key):
                sanitized[key] = None
                continue
            sanitized[key] = _redact_sensitive(_maybe_decode_json(value))
        if table == "platform_tokens":
            sanitized["encrypted_access_token"] = None
            sanitized["encrypted_refresh_token"] = None
        return sanitized

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return [row[0] for row in rows]

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        return [row[1] for row in rows]


def _maybe_decode_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _redact_sensitive(value: Any, key_hint: str | None = None) -> Any:
    if key_hint and SENSITIVE_KEY_PATTERN.search(key_hint):
        return None
    if isinstance(value, dict):
        return {
            key: _redact_sensitive(item, key)
            for key, item in value.items()
            if key not in SENSITIVE_COLUMNS
        }
    if isinstance(value, list):
        return [_redact_sensitive(item, key_hint) for item in value]
    return value


def _pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:64] or "backup"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create local token-safe backups and exports."
    )
    parser.add_argument("--database", help="Path to SQLite database.")
    parser.add_argument(
        "--type",
        default="full_local_backup",
        choices=sorted(BACKUP_TYPES),
        help="Backup/export type.",
    )
    parser.add_argument("--name", default=None, help="Human-readable backup name.")
    parser.add_argument("--include-media", action="store_true")
    parser.add_argument("--list", action="store_true", help="List backup history.")
    parser.add_argument("--preview-restore", help="Preview a backup restore path.")
    args = parser.parse_args()

    service = BackupService(args.database)
    if args.list:
        print(_pretty_json(service.list_backups()))
        return
    if args.preview_restore:
        print(_pretty_json(service.preview_restore(args.preview_restore)))
        return
    print(
        _pretty_json(
            service.create_backup(
                backup_type=args.type,
                backup_name=args.name,
                include_media=args.include_media,
            )
        )
    )


if __name__ == "__main__":
    main()
