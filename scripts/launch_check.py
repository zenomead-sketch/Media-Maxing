from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.db.init_db import REPO_ROOT, initialize_database, resolve_database_path
from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.jobs.local_runner import LocalJobRunner
from scripts.qa.integration_security_scan import SecurityScanResult, scan_paths
from scripts.services.ai_learning import AILearningService
from scripts.services.analytics import AnalyticsService
from scripts.services.backup import BackupService
from scripts.services.diagnostics import DiagnosticsService
from scripts.services.engagement import EngagementService
from scripts.services.manual_export import ManualExportError, ManualExportService
from scripts.services.reply_approvals import ReplyApprovalService
from scripts.services.reply_suggestions import ReplySuggestionService
from scripts.services.safety_center import SafetyCenterService


REQUIRED_CHECKLIST_SECTIONS = [
    "Install and setup",
    "Environment variables",
    "Database and seed",
    "Onboarding",
    "Brand Brain",
    "Media Library",
    "Generate",
    "Drafts and approvals",
    "Calendar",
    "Publish Queue",
    "Manual Export",
    "Connected Accounts mock mode",
    "Setup Wizard",
    "Analytics",
    "Engagement Inbox",
    "Reply suggestions",
    "AI learning loop",
    "Weekly reports",
    "Safety Center",
    "Emergency pause",
    "Backup and restore preview",
    "Diagnostics",
    "Desktop packaging",
    "Documentation",
    "Security scan",
    "Final build",
]

NODE_CHECK_FILES = [
    "apps/web/settings.js",
    "apps/web/generate.js",
    "apps/web/analytics.js",
    "apps/web/engagement.js",
    "apps/web/api-client.js",
]


@dataclass(frozen=True)
class LaunchCheck:
    id: str
    label: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)
    command: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LaunchCheckResult:
    status: str
    checkedAt: str
    databasePath: str
    artifactsDir: str
    checks: dict[str, LaunchCheck]
    security_scan: SecurityScanResult
    core_workflow_summary: str
    safety_summary: str
    known_blockers: list[str] = field(default_factory=list)
    next_fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checkedAt": self.checkedAt,
            "databasePath": self.databasePath,
            "artifactsDir": self.artifactsDir,
            "checks": {key: check.to_dict() for key, check in self.checks.items()},
            "securityScan": {
                **asdict(self.security_scan),
                "findings": [asdict(finding) for finding in self.security_scan.findings],
            },
            "coreWorkflowSummary": self.core_workflow_summary,
            "safetySummary": self.safety_summary,
            "knownBlockers": self.known_blockers,
            "nextFixes": self.next_fixes,
        }


def run_launch_check(
    *,
    database_path: str | Path | None = None,
    artifacts_dir: str | Path | None = None,
    repo_root: str | Path = REPO_ROOT,
    run_tests: bool = True,
    run_compile: bool = True,
    run_node_checks: bool = True,
) -> LaunchCheckResult:
    repo = Path(repo_root).resolve()
    checked_at = _utc_now()
    db_path = resolve_database_path(database_path)
    artifacts = (
        Path(artifacts_dir).expanduser().resolve()
        if artifacts_dir
        else repo / "data" / "launch-check" / _folder_timestamp()
    )
    artifacts.mkdir(parents=True, exist_ok=True)

    checks: dict[str, LaunchCheck] = {}
    blockers: list[str] = []
    fixes: list[str] = []

    checks["checklist_contract"] = _check_checklist_contract(repo)
    checks["database_and_seed"] = _check_database_and_seed(db_path)
    checks["core_workflow"] = _check_core_workflow(db_path, artifacts)
    checks["safety_workflow"] = _check_safety_workflow(db_path)
    checks["backup_and_diagnostics"] = _check_backup_and_diagnostics(db_path, artifacts)
    checks["security_scan"] = _check_security_scan(repo, artifacts)
    checks["tests"] = (
        _run_command_check(
            "tests",
            "Unit test suite",
            [sys.executable, "-m", "unittest", "discover", "tests"],
            repo,
        )
        if run_tests
        else _skipped("tests", "Unit test suite", "Skipped by --skip-tests.")
    )
    checks["compile"] = (
        _run_command_check(
            "compile",
            "Python compile check",
            [sys.executable, "-m", "compileall", "-q", "scripts", "tests", "apps/api"],
            repo,
        )
        if run_compile
        else _skipped("compile", "Python compile check", "Skipped by --skip-compile.")
    )
    checks["node_syntax"] = (
        _check_node_syntax(repo)
        if run_node_checks
        else _skipped("node_syntax", "Web JavaScript syntax", "Skipped by --skip-node-checks.")
    )
    checks["build"] = _check_build_script(repo)
    checks["desktop"] = _check_desktop_readiness(repo)

    for check in checks.values():
        if check.status == "fail":
            blockers.append(check.summary)
    if checks["build"].status == "partial":
        fixes.append("Add a package/build command when a frontend build tool is introduced.")
    if checks["desktop"].status == "partial":
        fixes.append("Finish Tauri/Electron packaging only after the web/local API path is stable.")
    if checks["security_scan"].status != "pass":
        fixes.append("Review the redacted security scan findings before local launch testing.")

    status = _overall_status(checks)
    return LaunchCheckResult(
        status=status,
        checkedAt=checked_at,
        databasePath=str(db_path),
        artifactsDir=str(artifacts),
        checks=checks,
        security_scan=scan_paths([repo, artifacts]),
        core_workflow_summary=checks["core_workflow"].summary,
        safety_summary=checks["safety_workflow"].summary,
        known_blockers=blockers,
        next_fixes=fixes,
    )


def _check_checklist_contract(repo: Path) -> LaunchCheck:
    doc = repo / "docs" / "launch-candidate-checklist.md"
    missing = []
    if not doc.exists():
        missing.append("docs/launch-candidate-checklist.md is missing.")
    else:
        text = doc.read_text(encoding="utf-8")
        for section in REQUIRED_CHECKLIST_SECTIONS:
            if section.lower() not in text.lower():
                missing.append(f"Checklist section missing: {section}")
    return LaunchCheck(
        id="checklist_contract",
        label="Launch checklist",
        status="fail" if missing else "pass",
        summary="Launch checklist exists and covers required sections."
        if not missing
        else "Launch checklist is incomplete.",
        details=missing,
    )


def _check_database_and_seed(db_path: Path) -> LaunchCheck:
    seed_demo_database(db_path)
    required_counts = {
        "brand_profiles": 1,
        "media_assets": 1,
        "generated_posts": 1,
        "scheduled_posts": 1,
        "publish_queue_items": 1,
        "approval_logs": 1,
    }
    details = []
    failures = []
    with closing(sqlite3.connect(db_path)) as connection:
        for table, minimum in required_counts.items():
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            details.append(f"{table}: {count}")
            if count < minimum:
                failures.append(f"{table} expected at least {minimum}, found {count}.")
    return LaunchCheck(
        id="database_and_seed",
        label="Database and seed",
        status="fail" if failures else "pass",
        summary="Clean launch database initialized and seeded."
        if not failures
        else "Launch database seed is incomplete.",
        details=details + failures,
        command=f"{sys.executable} -m scripts.db.init_db --database {db_path}; {sys.executable} -m scripts.db.seed_demo --database {db_path}",
    )


def _check_core_workflow(db_path: Path, artifacts: Path) -> LaunchCheck:
    details: list[str] = []
    failures: list[str] = []
    try:
        runner_summary = LocalJobRunner(db_path).run_once(
            now="2026-06-05T14:00:00Z",
            use_lock=False,
        )
        details.append(f"local_runner: due={runner_summary.dueChecked}, ready={runner_summary.queueReady}, blocked={runner_summary.queueBlocked}")

        analytics = AnalyticsService(db_path).generate_mock_snapshots(
            brand_profile_id=DEMO_BRAND_ID,
            explicitly_requested=True,
        )
        details.append(f"mock_analytics: created={analytics.createdCount}, skipped={analytics.skippedCount}")

        engagement = EngagementService(db_path).ingest_mock_engagement(
            brand_profile_id=DEMO_BRAND_ID
        )
        details.append(f"mock_engagement: created={engagement.createdCount}, skipped={engagement.skippedCount}")

        engagement_id = _first_engagement_item(db_path, exclude_intent="spam")
        if engagement_id:
            suggestion = ReplySuggestionService(db_path).generate(
                engagement_item_id=engagement_id,
                provider_name="mock",
            )
            ReplyApprovalService(db_path).approve(
                suggestion_id=suggestion.id,
                reason="Launch candidate local approval smoke test.",
                actor_type="test",
            )
            details.append("reply_suggestion: generated and approved locally")
        else:
            failures.append("No non-spam engagement item found for reply suggestion.")

        learning = AILearningService(db_path)
        insights = learning.generateContentInsights(brandProfileId=DEMO_BRAND_ID)
        memory = learning.updateLearningMemory(brandProfileId=DEMO_BRAND_ID)
        report = learning.generateWeeklyReport(
            brandProfileId=DEMO_BRAND_ID,
            weekStartDate="2026-05-25",
        )
        details.append(
            "insights="
            f"{len(insights)}, memory_created={memory.createdCount}, "
            f"memory_updated={memory.updatedCount}, weekly_report={report.id}"
        )

        export_id = _exportable_queue_item(db_path)
        if export_id:
            try:
                result = ManualExportService(db_path, export_root=artifacts / "manual-posts").export_queue_item(export_id)
                details.append(f"manual_export: {result.exportPath}")
            except ManualExportError as exc:
                failures.append(f"Manual export smoke failed: {exc}")
        else:
            failures.append("No exportable queue item found.")
    except Exception as exc:  # pragma: no cover - defensive launch reporting
        failures.append(f"{type(exc).__name__}: {exc}")

    return LaunchCheck(
        id="core_workflow",
        label="Core local workflow",
        status="fail" if failures else "pass",
        summary="Core local workflow smoke passed without real APIs or publishing."
        if not failures
        else "Core local workflow smoke found blockers.",
        details=details + failures,
    )


def _check_safety_workflow(db_path: Path) -> LaunchCheck:
    details: list[str] = []
    failures: list[str] = []
    try:
        service = SafetyCenterService(db_path)
        service.set_emergency_pause(True, actor_type="test", reason="Launch candidate safety gate.")
        paused_state = service.get_state()
        runner_summary = LocalJobRunner(db_path).run_once(use_lock=False)
        if not paused_state["emergencyPause"]["enabled"]:
            failures.append("Emergency pause did not enable.")
        if paused_state["publishingSafety"]["realPublishingEnabled"]:
            failures.append("Real publishing is unexpectedly enabled.")
        if not runner_summary.notes and runner_summary.queueReady:
            failures.append("Runner marked queue ready while emergency pause was enabled.")
        details.append("emergency_pause: enabled")
        details.append(f"runner_while_paused: ready={runner_summary.queueReady}, blocked={runner_summary.queueBlocked}, notes={runner_summary.notes}")

        service.set_emergency_pause(False, actor_type="test", reason="Launch candidate safety gate reset.")
        unpaused_state = service.get_state()
        if unpaused_state["emergencyPause"]["enabled"]:
            failures.append("Emergency pause did not disable.")
        audit_count = _safety_audit_count(db_path)
        if audit_count < 2:
            failures.append("Expected safety audit log entries for pause enable/disable.")
        details.append(f"safety_audit_logs={audit_count}")
        details.append("real publishing remains disabled; replies are not sent automatically")
    except Exception as exc:  # pragma: no cover - defensive launch reporting
        failures.append(f"{type(exc).__name__}: {exc}")

    return LaunchCheck(
        id="safety_workflow",
        label="Safety workflow",
        status="fail" if failures else "pass",
        summary="Emergency pause and audit smoke passed; real publishing remains disabled."
        if not failures
        else "Safety workflow smoke found blockers.",
        details=details + failures,
    )


def _check_backup_and_diagnostics(db_path: Path, artifacts: Path) -> LaunchCheck:
    details: list[str] = []
    failures: list[str] = []
    try:
        backup = BackupService(db_path).create_backup(
            backup_type="full_local_backup",
            backup_name="launch-check",
            include_media=False,
        )
        details.append(f"backup={backup['backupPath']}")
        diagnostics = DiagnosticsService(db_path).export_report()
        details.append(f"diagnostics={diagnostics['reportPath']}")
        scan = scan_paths([backup["backupPath"], diagnostics["reportPath"], artifacts])
        details.append(scan.to_report())
        if scan.actual_secret_like_values:
            failures.append("Backup or diagnostics export contains secret-like values.")
    except Exception as exc:  # pragma: no cover - defensive launch reporting
        failures.append(f"{type(exc).__name__}: {exc}")
    return LaunchCheck(
        id="backup_and_diagnostics",
        label="Backup and diagnostics",
        status="fail" if failures else "pass",
        summary="Backup and diagnostics exports were created and scanned."
        if not failures
        else "Backup or diagnostics export failed safety checks.",
        details=details + failures,
    )


def _check_security_scan(repo: Path, artifacts: Path) -> LaunchCheck:
    result = scan_paths([repo, artifacts])
    return LaunchCheck(
        id="security_scan",
        label="Security scan",
        status="fail" if result.actual_secret_like_values else "pass",
        summary="No actual secret-like values found by the redacted scanner."
        if not result.actual_secret_like_values
        else "Potential secret-like values found; review locally.",
        details=[result.to_report()],
        command=f"{sys.executable} -m scripts.qa.integration_security_scan . {artifacts}",
    )


def _check_node_syntax(repo: Path) -> LaunchCheck:
    missing = [path for path in NODE_CHECK_FILES if not (repo / path).exists()]
    if missing:
        return LaunchCheck(
            id="node_syntax",
            label="Web JavaScript syntax",
            status="fail",
            summary="Expected web JavaScript files are missing.",
            details=missing,
        )
    failures = []
    for path in NODE_CHECK_FILES:
        completed = subprocess.run(
            ["node", "--check", path],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            failures.append(_safe_command_output(path, completed.stderr or completed.stdout))
    return LaunchCheck(
        id="node_syntax",
        label="Web JavaScript syntax",
        status="fail" if failures else "pass",
        summary="Web JavaScript syntax checks passed." if not failures else "Web JavaScript syntax check failed.",
        details=failures,
        command="; ".join(f"node --check {path}" for path in NODE_CHECK_FILES),
    )


def _check_build_script(repo: Path) -> LaunchCheck:
    package_json = repo / "package.json"
    if not package_json.exists():
        return LaunchCheck(
            id="build",
            label="Final build",
            status="partial",
            summary="No package.json/build script exists for this static web MVP.",
            details=["Use Python local server and syntax/unit checks for this launch candidate."],
        )
    return _run_command_check("build", "Final build", ["npm", "run", "build"], repo)


def _check_desktop_readiness(repo: Path) -> LaunchCheck:
    readiness = repo / "apps" / "desktop" / "desktop-readiness.json"
    docs = repo / "docs" / "desktop-packaging.md"
    details = []
    if readiness.exists():
        details.append(str(readiness))
    if docs.exists():
        details.append(str(docs))
    return LaunchCheck(
        id="desktop",
        label="Desktop packaging",
        status="partial" if details else "fail",
        summary="Desktop packaging is documented/prepared, but no production installer build is configured yet."
        if details
        else "Desktop packaging readiness files are missing.",
        details=details or ["Add desktop packaging readiness docs/config before installer testing."],
    )


def _run_command_check(
    check_id: str,
    label: str,
    command: list[str],
    cwd: Path,
) -> LaunchCheck:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    output = _safe_command_output(" ".join(command), completed.stdout + completed.stderr)
    return LaunchCheck(
        id=check_id,
        label=label,
        status="pass" if completed.returncode == 0 else "fail",
        summary=f"{label} passed." if completed.returncode == 0 else f"{label} failed.",
        details=[output] if output else [],
        command=" ".join(command),
    )


def _skipped(check_id: str, label: str, reason: str) -> LaunchCheck:
    return LaunchCheck(
        id=check_id,
        label=label,
        status="partial",
        summary=reason,
        details=[reason],
    )


def _first_engagement_item(db_path: Path, *, exclude_intent: str) -> str | None:
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT id
            FROM engagement_items
            WHERE intent != ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (exclude_intent,),
        ).fetchone()
    return row[0] if row else None


def _exportable_queue_item(db_path: Path) -> str | None:
    with closing(sqlite3.connect(db_path)) as connection:
        row = connection.execute(
            """
            SELECT id
            FROM publish_queue_items
            WHERE queue_status IN ('waiting', 'ready')
              AND COALESCE(preflight_status, 'not_checked') NOT IN ('errors', 'blocked', 'failed')
            ORDER BY CASE queue_status WHEN 'ready' THEN 0 ELSE 1 END, created_at ASC
            LIMIT 1
            """
        ).fetchone()
    return row[0] if row else None


def _safety_audit_count(db_path: Path) -> int:
    with closing(sqlite3.connect(db_path)) as connection:
        return connection.execute("SELECT COUNT(*) FROM safety_audit_logs").fetchone()[0]


def _overall_status(checks: dict[str, LaunchCheck]) -> str:
    statuses = {check.status for check in checks.values()}
    if "fail" in statuses:
        return "fail"
    if "partial" in statuses:
        return "partial"
    return "pass"


def _safe_command_output(label: str, output: str, *, max_chars: int = 1600) -> str:
    text = output.strip()
    for marker in (
        "access_token",
        "refresh_token",
        "client_secret",
        "Authorization",
        "Bearer",
        "id_token",
        "appsecret_proof",
        "signed_request",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        text = text.replace(marker, "[REDACTED_MARKER]")
    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"
    return f"{label}: {text}" if text else ""


def _folder_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the local launch candidate QA smoke checks. "
            "No real APIs are called and no real publishing/replies are sent."
        )
    )
    parser.add_argument("--database", help="SQLite database path for the launch check.")
    parser.add_argument("--artifacts-dir", help="Directory for launch check artifacts.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip full unittest discovery.")
    parser.add_argument("--skip-compile", action="store_true", help="Skip Python compileall.")
    parser.add_argument("--skip-node-checks", action="store_true", help="Skip node --check syntax checks.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_launch_check(
        database_path=args.database,
        artifacts_dir=args.artifacts_dir,
        run_tests=not args.skip_tests,
        run_compile=not args.skip_compile,
        run_node_checks=not args.skip_node_checks,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_human_report(payload))
    return 1 if result.status == "fail" else 0


def _human_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Launch candidate status: {payload['status']}",
        f"Checked at: {payload['checkedAt']}",
        f"Database: {payload['databasePath']}",
        f"Artifacts: {payload['artifactsDir']}",
        "",
        "Checks:",
    ]
    for check in payload["checks"].values():
        lines.append(f"- {check['label']}: {check['status']} - {check['summary']}")
    lines.extend(
        [
            "",
            "Security scan:",
            f"- actual_secret_like_values={payload['securityScan']['actual_secret_like_values']}",
            "- No secret values are printed by this report.",
            "",
            f"Core workflow: {payload['coreWorkflowSummary']}",
            f"Safety workflow: {payload['safetySummary']}",
        ]
    )
    if payload["knownBlockers"]:
        lines.append("")
        lines.append("Known blockers:")
        lines.extend(f"- {blocker}" for blocker in payload["knownBlockers"])
    if payload["nextFixes"]:
        lines.append("")
        lines.append("Smallest next fixes:")
        lines.extend(f"- {fix}" for fix in payload["nextFixes"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
