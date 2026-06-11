from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from scripts.db.init_db import MIGRATIONS_DIR, REPO_ROOT, initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings
from scripts.services.backup import BackupService
from scripts.services.integration_setup import validate_social_integration_setup
from scripts.services.onboarding import OnboardingService
from scripts.services.platform_http_client import redact_http_value, redact_raw_text
from scripts.services.safety_center import SafetyCenterService


DIAGNOSTIC_STATUSES = {"healthy", "warning", "error", "disabled", "unknown"}


@dataclass(frozen=True)
class DiagnosticResult:
    id: str
    label: str
    status: str
    summary: str
    details: str
    recommendedAction: str
    checkedAt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "summary": redact_diagnostic_text(self.summary),
            "details": redact_diagnostic_text(self.details),
            "recommendedAction": redact_diagnostic_text(self.recommendedAction),
            "checkedAt": self.checkedAt,
        }


class DiagnosticsService:
    """Local app diagnostics with token-safe report export."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def run_checks(self, *, recent_errors: list[str] | None = None) -> dict[str, Any]:
        checked_at = _utc_now()
        settings = load_app_settings(self.database_path)
        local_data_dir = _resolve_local_data_directory(settings.localDataDirectory)
        integration = validate_social_integration_setup()
        safety = SafetyCenterService(self.database_path).get_state()
        checklist = OnboardingService(self.database_path).get_state().checklist

        sections: list[tuple[str, str, list[DiagnosticResult]]] = [
            (
                "local_storage",
                "Local storage",
                [
                    self._result(
                        "app_version",
                        "App version",
                        "unknown",
                        "No package version is configured yet.",
                        "Version metadata is not available in this static/local MVP.",
                        "Add an app version during desktop packaging readiness.",
                        checked_at,
                    ),
                    self._result(
                        "app_environment",
                        "App environment",
                        "healthy" if settings.appEnvironment else "unknown",
                        settings.appEnvironment or "Unknown environment",
                        "This comes from app settings or APP_ENV.",
                        "Use development or test locally; production comes later.",
                        checked_at,
                    ),
                    self._path_result(
                        "local_data_directory_exists",
                        "Local data directory exists",
                        local_data_dir,
                        must_exist=True,
                        checked_at=checked_at,
                    ),
                    self._writable_result(local_data_dir, checked_at),
                    self._path_result(
                        "media_directory_exists",
                        "Media directory exists",
                        local_data_dir / "media",
                        must_exist=True,
                        checked_at=checked_at,
                    ),
                    self._path_result(
                        "export_directory_exists",
                        "Export directory exists",
                        local_data_dir / "exports",
                        must_exist=True,
                        checked_at=checked_at,
                    ),
                    self._path_result(
                        "logs_directory_exists",
                        "Logs directory exists",
                        local_data_dir / "logs",
                        must_exist=True,
                        checked_at=checked_at,
                    ),
                    self._path_result(
                        "backup_directory_exists",
                        "Backup directory exists",
                        local_data_dir / "exports" / "backups",
                        must_exist=True,
                        checked_at=checked_at,
                    ),
                ],
            ),
            (
                "database",
                "Database",
                [
                    self._database_reachable_result(checked_at),
                    self._migration_result(checked_at),
                ],
            ),
            (
                "ai",
                "AI",
                [
                    self._result(
                        "ai_provider_status",
                        "AI provider status",
                        "healthy" if settings.aiProviderPreference == "mock" else "warning",
                        f"AI provider preference is {settings.aiProviderPreference}.",
                        "Mock mode is the safe local default.",
                        "Keep mock selected unless real provider keys are intentionally configured later.",
                        checked_at,
                    ),
                    self._result(
                        "mock_ai_provider_available",
                        "Mock AI provider available",
                        "healthy",
                        "Mock AI is available for local generation and tests.",
                        "No API key is required.",
                        "Use mock mode for local QA.",
                        checked_at,
                    ),
                ],
            ),
            (
                "social_integrations",
                "Social integrations",
                [
                    self._result(
                        "integration_mode",
                        "Integration mode",
                        "disabled" if integration.integrationsMode == "disabled" else "healthy",
                        f"Integration mode is {integration.integrationsMode}.",
                        "Mock and scaffolded connectors are local-safe by default.",
                        "Use Social Integration Setup before enabling any real OAuth flags.",
                        checked_at,
                    ),
                    self._result(
                        "real_publishing_disabled",
                        "Real publishing disabled",
                        "healthy",
                        "Real publishing is disabled by policy.",
                        "Even if an environment flag requests it, this batch keeps real publishing unavailable.",
                        "Continue using manual export until a future explicit real-publishing batch.",
                        checked_at,
                    ),
                    self._result(
                        "connected_account_summary",
                        "Connected account summary",
                        "healthy",
                        self._connected_account_summary(),
                        "Only token-safe account counts are included.",
                        "Use Connected Accounts to inspect individual mock or scaffolded connections.",
                        checked_at,
                    ),
                    self._result(
                        "token_storage_mode",
                        "Token storage mode",
                        "healthy"
                        if integration.tokenStorageMode == "placeholder_not_stored"
                        else "warning",
                        f"Token storage mode is {integration.tokenStorageMode}.",
                        "Raw tokens are not stored in the safe MVP placeholder mode.",
                        "Use a secure keychain/encrypted mode before real OAuth is used for production.",
                        checked_at,
                    ),
                    self._secret_exposure_result(checked_at),
                ],
            ),
            (
                "safety",
                "Safety",
                [
                    self._result(
                        "emergency_pause_status",
                        "Emergency pause status",
                        "warning" if safety["emergencyPause"]["enabled"] else "healthy",
                        "Emergency pause is on." if safety["emergencyPause"]["enabled"] else "Emergency pause is off.",
                        "Pause blocks scheduling, queue readiness, mock publishing, and future real automation.",
                        "Use Safety Center to change pause state with confirmation.",
                        checked_at,
                    ),
                    self._result(
                        "automation_level_status",
                        "Automation level",
                        "healthy" if safety["automationLevel"] == "approval_queue" else "warning",
                        f"Automation level is {safety['automationLevel']}.",
                        "Modes above approval_queue remain planned/locked for real publishing and replies.",
                        "Keep approval_queue for MVP safety.",
                        checked_at,
                    ),
                    self._result(
                        "critical_safety_flags_summary",
                        "Critical safety flags",
                        "warning" if safety["criticalSafetyFlags"]["total"] else "healthy",
                        f"{safety['criticalSafetyFlags']['total']} critical safety flags are currently visible.",
                        "Diagnostics only reports counts and does not hide safety issues.",
                        "Review Drafts, Publish Queue, and Safety Center for details.",
                        checked_at,
                    ),
                    self._result(
                        "pending_approvals_summary",
                        "Pending approvals",
                        "warning"
                        if any(int(value or 0) for value in safety["pendingApprovals"].values())
                        else "healthy",
                        _pending_approval_summary(safety["pendingApprovals"]),
                        "Human approval remains required for drafts and reply suggestions.",
                        "Open Drafts or Engagement Inbox to clear review items.",
                        checked_at,
                    ),
                ],
            ),
            (
                "queue_jobs",
                "Queue and jobs",
                [
                    self._job_runner_result(checked_at),
                    self._queue_count_result(checked_at),
                ],
            ),
            (
                "content_workflow",
                "Content workflow",
                [
                    self._count_result(
                        "drafts_needing_review_count",
                        "Drafts needing review",
                        "generated_posts",
                        "approval_status IN ('needs_review', 'revision_requested')",
                        checked_at,
                        warning_if_positive=True,
                        action="Open Drafts to approve, revise, or archive local drafts.",
                    ),
                    self._count_result(
                        "engagement_needing_reply_count",
                        "Engagement needing reply",
                        "engagement_items",
                        "status IN ('new', 'needs_reply', 'reply_suggested') AND requires_response = 1",
                        checked_at,
                        warning_if_positive=True,
                        action="Open Engagement Inbox to review local reply workflow.",
                    ),
                    self._analytics_result(checked_at),
                    self._setup_checklist_result(checklist, checked_at),
                ],
            ),
            (
                "backups",
                "Backups",
                [
                    self._backup_result(checked_at),
                ],
            ),
            (
                "recent_errors",
                "Recent errors",
                [
                    self._recent_errors_result(recent_errors or [], checked_at),
                ],
            ),
        ]

        flat_results = [result.to_dict() for _, _, results in sections for result in results]
        section_dicts = [
            {
                "id": section_id,
                "label": label,
                "results": [result.to_dict() for result in results],
            }
            for section_id, label, results in sections
        ]
        summary = _status_summary(flat_results)
        return {
            "checkedAt": checked_at,
            "overallStatus": _overall_status(summary),
            "summary": summary,
            "sections": section_dicts,
            "results": flat_results,
            "nextSteps": _next_steps(flat_results),
            "recentErrors": [redact_diagnostic_text(error) for error in recent_errors or []],
            "localOnly": True,
            "redactionNotice": "Diagnostics reports redact tokens, secrets, authorization codes, and raw provider credentials.",
        }

    def export_report(self, *, recent_errors: list[str] | None = None) -> dict[str, Any]:
        diagnostics = self.run_checks(recent_errors=recent_errors)
        settings = load_app_settings(self.database_path)
        local_data_dir = _resolve_local_data_directory(settings.localDataDirectory)
        report_dir = local_data_dir / "exports" / "diagnostics"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M")
        report_path = report_dir / f"diagnostic-report-{stamp}.md"
        report_path.write_text(
            _markdown_report(diagnostics, local_data_dir=local_data_dir),
            encoding="utf-8",
        )
        return {
            "reportPath": str(report_path),
            "createdAt": diagnostics["checkedAt"],
            "overallStatus": diagnostics["overallStatus"],
            "redactionNotice": diagnostics["redactionNotice"],
        }

    def _result(
        self,
        id: str,
        label: str,
        status: str,
        summary: str,
        details: str,
        recommended_action: str,
        checked_at: str,
    ) -> DiagnosticResult:
        if status not in DIAGNOSTIC_STATUSES:
            status = "unknown"
        return DiagnosticResult(
            id=id,
            label=label,
            status=status,
            summary=summary,
            details=details,
            recommendedAction=recommended_action,
            checkedAt=checked_at,
        )

    def _path_result(
        self,
        id: str,
        label: str,
        path: Path,
        *,
        must_exist: bool,
        checked_at: str,
    ) -> DiagnosticResult:
        exists = path.exists()
        return self._result(
            id,
            label,
            "healthy" if exists else "warning" if must_exist else "unknown",
            f"{path} exists." if exists else f"{path} is missing.",
            "Local path check only. No cloud upload or external calls are used.",
            "Create the folder or use Backup & Data/onboarding to initialize local data paths."
            if not exists
            else "No action needed.",
            checked_at,
        )

    def _writable_result(self, path: Path, checked_at: str) -> DiagnosticResult:
        if not path.exists():
            return self._result(
                "local_data_directory_writable",
                "Local data directory writable",
                "warning",
                "Local data directory is missing, so writability could not be confirmed.",
                str(path),
                "Create the local data directory or confirm the path in Settings.",
                checked_at,
            )
        try:
            probe = path / ".diagnostics-write-check"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return self._result(
                "local_data_directory_writable",
                "Local data directory writable",
                "healthy",
                "Local data directory is writable.",
                str(path),
                "No action needed.",
                checked_at,
            )
        except OSError as error:
            return self._result(
                "local_data_directory_writable",
                "Local data directory writable",
                "error",
                "Local data directory is not writable.",
                str(error),
                "Choose a writable local folder in Settings or fix folder permissions.",
                checked_at,
            )

    def _database_reachable_result(self, checked_at: str) -> DiagnosticResult:
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                connection.execute("SELECT 1").fetchone()
            return self._result(
                "sqlite_database_reachable",
                "SQLite database reachable",
                "healthy",
                "SQLite database opened successfully.",
                str(self.database_path),
                "No action needed.",
                checked_at,
            )
        except sqlite3.Error as error:
            return self._result(
                "sqlite_database_reachable",
                "SQLite database reachable",
                "error",
                "SQLite database could not be opened.",
                str(error),
                "Run database initialization or restore from a backup.",
                checked_at,
            )

    def _migration_result(self, checked_at: str) -> DiagnosticResult:
        try:
            expected = {path.stem for path in MIGRATIONS_DIR.glob("*.sql")}
            with closing(sqlite3.connect(self.database_path)) as connection:
                rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
            applied = {str(row[0]) for row in rows}
            missing = sorted(expected - applied)
            return self._result(
                "database_migrations_status",
                "Database migrations status",
                "healthy" if not missing else "warning",
                f"{len(applied)} migration(s) applied; {len(missing)} missing.",
                "Missing versions: " + ", ".join(missing) if missing else "All local migrations are applied.",
                "Run the database initialization command if migrations are missing."
                if missing
                else "No action needed.",
                checked_at,
            )
        except sqlite3.Error as error:
            return self._result(
                "database_migrations_status",
                "Database migrations status",
                "error",
                "Migration status could not be read.",
                str(error),
                "Run database initialization or inspect the local SQLite file.",
                checked_at,
            )

    def _connected_account_summary(self) -> str:
        if not self._table_exists("social_accounts"):
            return "Connected account table is not available."
        rows = self._fetchall(
            "SELECT connection_status, COUNT(*) AS count FROM social_accounts GROUP BY connection_status"
        )
        if not rows:
            return "No connected accounts saved locally."
        return ", ".join(f"{row['connection_status']}: {row['count']}" for row in rows)

    def _secret_exposure_result(self, checked_at: str) -> DiagnosticResult:
        token_rows = self._count("platform_tokens") if self._table_exists("platform_tokens") else 0
        return self._result(
            "secret_exposure_safety",
            "Secret exposure safety check",
            "healthy",
            "Diagnostics do not expose tokens, client secrets, authorization codes, or encrypted token blobs.",
            f"{token_rows} token metadata row(s) exist server-side. Values are not queried or reported.",
            "Keep using safe DTOs and never paste secrets into diagnostics reports.",
            checked_at,
        )

    def _job_runner_result(self, checked_at: str) -> DiagnosticResult:
        attempts = self._fetchall(
            """
            SELECT attempt_type, attempt_status, created_at
            FROM publish_attempts
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        locks = self._count("local_job_locks") if self._table_exists("local_job_locks") else 0
        if not attempts:
            return self._result(
                "job_runner_status",
                "Job runner status",
                "unknown",
                "No local job runner execution has been recorded yet.",
                f"Active local job lock rows: {locks}.",
                "Run the local job runner once when testing scheduled queue readiness.",
                checked_at,
            )
        attempt = attempts[0]
        return self._result(
            "job_runner_status",
            "Job runner status",
            "healthy" if attempt["attempt_status"] in {"succeeded", "blocked", "skipped"} else "warning",
            f"Last recorded job attempt was {attempt['attempt_type']} with status {attempt['attempt_status']}.",
            f"Last job runner execution: {attempt['created_at']}. Active local job lock rows: {locks}.",
            "Review Publish Queue if recent attempts failed or were blocked.",
            checked_at,
        )

    def _queue_count_result(self, checked_at: str) -> DiagnosticResult:
        count = self._count("publish_queue_items", "queue_status = 'blocked'")
        return self._result(
            "queue_blocked_count",
            "Queue blocked count",
            "warning" if count else "healthy",
            f"{count} publish queue item(s) are blocked.",
            "Blocked queue items stay local and are not published.",
            "Open Publish Queue to review preflight errors and warnings." if count else "No action needed.",
            checked_at,
        )

    def _count_result(
        self,
        id: str,
        label: str,
        table: str,
        where: str,
        checked_at: str,
        *,
        warning_if_positive: bool,
        action: str,
    ) -> DiagnosticResult:
        count = self._count(table, where) if self._table_exists(table) else 0
        return self._result(
            id,
            label,
            "warning" if warning_if_positive and count else "healthy",
            f"{count} item(s) found.",
            f"Table checked: {table}.",
            action if count else "No action needed.",
            checked_at,
        )

    def _analytics_result(self, checked_at: str) -> DiagnosticResult:
        count = self._count("analytics_snapshots") if self._table_exists("analytics_snapshots") else 0
        return self._result(
            "analytics_data_availability",
            "Analytics data availability",
            "healthy" if count else "warning",
            f"{count} analytics snapshot(s) are stored locally.",
            "Manual analytics use source=manual; demo analytics use source=mock.",
            "Add manual metrics or generate mock analytics to populate the Analytics dashboard."
            if not count
            else "No action needed.",
            checked_at,
        )

    def _setup_checklist_result(self, checklist: list[dict[str, Any]], checked_at: str) -> DiagnosticResult:
        total = len(checklist)
        completed = sum(1 for item in checklist if item.get("status") == "completed")
        needs_attention = sum(1 for item in checklist if item.get("status") == "needs_attention")
        return self._result(
            "setup_checklist_status",
            "Setup checklist status",
            "warning" if needs_attention or completed < total else "healthy",
            f"{completed} of {total} setup checklist item(s) are complete.",
            f"{needs_attention} item(s) need attention.",
            "Open Home or Onboarding to continue setup." if completed < total else "No action needed.",
            checked_at,
        )

    def _backup_result(self, checked_at: str) -> DiagnosticResult:
        try:
            backups = BackupService(self.database_path).list_backups()
        except Exception as error:
            return self._result(
                "backup_availability",
                "Backup availability",
                "warning",
                "Backup history could not be read.",
                str(error),
                "Open Backup & Data to create a fresh backup.",
                checked_at,
            )
        return self._result(
            "backup_availability",
            "Backup availability",
            "healthy" if backups else "warning",
            f"{len(backups)} backup(s) found.",
            "Backups are local and exclude raw tokens/secrets by default.",
            "Create a full local backup from Backup & Data." if not backups else "No action needed.",
            checked_at,
        )

    def _recent_errors_result(self, recent_errors: list[str], checked_at: str) -> DiagnosticResult:
        count = len(recent_errors)
        return self._result(
            "recent_safe_errors",
            "Recent safe errors",
            "warning" if count else "healthy",
            f"{count} recent browser/API error(s) were included.",
            "\n".join(redact_diagnostic_text(error) for error in recent_errors[:5])
            if recent_errors
            else "No recent safe errors were provided.",
            "Use Copy diagnostic summary or export a report when asking for help."
            if count
            else "No action needed.",
            checked_at,
        )

    def _table_exists(self, table_name: str) -> bool:
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
        return row is not None

    def _count(self, table_name: str, where: str | None = None) -> int:
        if not self._table_exists(table_name):
            return 0
        sql = f"SELECT COUNT(*) FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        with closing(sqlite3.connect(self.database_path)) as connection:
            return int(connection.execute(sql).fetchone()[0])

    def _fetchall(self, sql: str) -> list[sqlite3.Row]:
        try:
            with closing(sqlite3.connect(self.database_path)) as connection:
                connection.row_factory = sqlite3.Row
                return list(connection.execute(sql).fetchall())
        except sqlite3.Error:
            return []


def redact_diagnostic_text(value: Any) -> str:
    redacted = redact_raw_text(str(redact_http_value(value).value))
    return re.sub(r"(Authorization:\s*\[REDACTED\])\s+\S+", r"\1", redacted, flags=re.IGNORECASE)


def _resolve_local_data_directory(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _status_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status: sum(1 for result in results if result["status"] == status)
        for status in sorted(DIAGNOSTIC_STATUSES)
    }


def _overall_status(summary: dict[str, int]) -> str:
    if summary.get("error", 0):
        return "error"
    if summary.get("warning", 0):
        return "warning"
    if summary.get("unknown", 0):
        return "unknown"
    return "healthy"


def _next_steps(results: list[dict[str, Any]]) -> list[str]:
    steps = [
        result["recommendedAction"]
        for result in results
        if result["status"] in {"error", "warning", "unknown"} and result["recommendedAction"] != "No action needed."
    ]
    deduped: list[str] = []
    for step in steps:
        if step not in deduped:
            deduped.append(step)
    return deduped[:8] or ["No urgent action needed. Keep backups current and use manual export until real publishing is enabled."]


def _pending_approval_summary(pending: dict[str, Any]) -> str:
    return (
        f"{pending.get('draftsNeedingReview', 0)} draft(s), "
        f"{pending.get('replySuggestionsNeedingReview', 0)} reply suggestion(s), "
        f"{pending.get('queueItemsNeedingAttention', 0)} queue item(s) need attention."
    )


def _markdown_report(diagnostics: dict[str, Any], *, local_data_dir: Path) -> str:
    lines = [
        "# Diagnostics Report",
        "",
        f"- Timestamp: {diagnostics['checkedAt']}",
        f"- App environment: {_result_summary(diagnostics, 'app_environment')}",
        f"- Local data directory: {redact_diagnostic_text(local_data_dir)}",
        f"- Overall status: {diagnostics['overallStatus']}",
        "",
        "## Redaction notice",
        diagnostics["redactionNotice"],
        "",
        "## Health results",
    ]
    for section in diagnostics["sections"]:
        lines.extend(["", f"### {section['label']}"])
        for result in section["results"]:
            lines.append(
                f"- {result['label']}: {result['status']} - {result['summary']}"
            )
            if result["recommendedAction"] != "No action needed.":
                lines.append(f"  - Next: {result['recommendedAction']}")
    lines.extend(["", "## What to do next"])
    lines.extend(f"- {step}" for step in diagnostics["nextSteps"])
    lines.extend(["", "## Recent safe errors"])
    if diagnostics["recentErrors"]:
        lines.extend(f"- {redact_diagnostic_text(error)}" for error in diagnostics["recentErrors"])
    else:
        lines.append("- No recent safe errors were included.")
    lines.extend(
        [
            "",
            "## Safety state",
            f"- Emergency pause: {_result_summary(diagnostics, 'emergency_pause_status')}",
            f"- Real publishing: {_result_summary(diagnostics, 'real_publishing_disabled')}",
            "",
            "This report is local-only. It does not upload diagnostics or include media contents.",
        ]
    )
    return redact_diagnostic_text("\n".join(lines)) + "\n"


def _result_summary(diagnostics: dict[str, Any], result_id: str) -> str:
    for result in diagnostics["results"]:
        if result["id"] == result_id:
            return result["summary"]
    return "Unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run or export local app diagnostics.")
    parser.add_argument("--database", help="Path to the SQLite database.")
    parser.add_argument("--export", action="store_true", help="Write a redacted diagnostics report.")
    args = parser.parse_args()

    service = DiagnosticsService(args.database)
    payload = service.export_report() if args.export else service.run_checks()
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
