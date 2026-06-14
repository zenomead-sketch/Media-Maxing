from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from apps.api.local_server import LocalApiApplication
from scripts.db.init_db import REPO_ROOT
from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database


@dataclass(frozen=True)
class DemoDayStep:
    id: str
    label: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DemoDayResult:
    status: str
    checkedAt: str
    databasePath: str
    artifactsDir: str
    controlCenterRoute: str
    realPublishingEnabled: bool
    realReplySendingEnabled: bool
    realSocialApisEnabled: bool
    steps: list[DemoDayStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checkedAt": self.checkedAt,
            "databasePath": self.databasePath,
            "artifactsDir": self.artifactsDir,
            "controlCenterRoute": self.controlCenterRoute,
            "realPublishingEnabled": self.realPublishingEnabled,
            "realReplySendingEnabled": self.realReplySendingEnabled,
            "realSocialApisEnabled": self.realSocialApisEnabled,
            "steps": [step.to_dict() for step in self.steps],
        }


class DemoDayContext:
    def __init__(self, *, database_path: Path, artifacts_dir: Path):
        self.database_path = database_path
        self.artifacts_dir = artifacts_dir
        self.app = LocalApiApplication(database_path)
        self.bundle: dict[str, Any] | None = None
        self.draft_id: str | None = None
        self.scheduled_post_id: str | None = None
        self.queue_item_id: str | None = None
        self.engagement_item_id = "mock-engagement-praise-comment"
        self.reply_suggestion_id: str | None = None


def run_demo_day_check(
    *,
    database_path: str | Path | None = None,
    artifacts_dir: str | Path | None = None,
) -> DemoDayResult:
    created_temp = None
    if artifacts_dir:
        artifacts = Path(artifacts_dir).expanduser().resolve()
    else:
        artifacts = REPO_ROOT / "data" / "demo-day-check" / _folder_timestamp()
    artifacts.mkdir(parents=True, exist_ok=True)

    if database_path:
        db_path = Path(database_path).expanduser().resolve()
    else:
        created_temp = tempfile.TemporaryDirectory()
        db_path = Path(created_temp.name) / "demo-day.sqlite"

    seed_demo_database(db_path)
    context = DemoDayContext(database_path=db_path, artifacts_dir=artifacts)
    steps: list[DemoDayStep] = []

    workflow: list[tuple[str, str, Callable[[DemoDayContext], list[str]]]] = [
        ("onboarding", "Complete guided onboarding", _step_onboarding),
        ("media", "Confirm Media Library has demo media", _step_media),
        ("generate", "Generate mock content", _step_generate),
        ("drafts", "Save generated draft and approve locally", _step_drafts),
        ("calendar", "Schedule approved draft locally", _step_calendar),
        ("queue", "Run queue preflight", _step_queue),
        ("manual_export", "Create manual export package and mark exported", _step_manual_export),
        ("analytics", "Enter manual analytics", _step_analytics),
        ("engagement", "Generate mock engagement", _step_engagement),
        ("reply_suggestion", "Generate and approve reply locally", _step_reply_suggestion),
        ("learning", "Refresh AI memory and weekly report", _step_learning),
        ("backup", "Create local backup", _step_backup),
        ("diagnostics", "Export diagnostic report", _step_diagnostics),
        ("safety", "Confirm real publishing and replies are disabled", _step_safety),
    ]

    for step_id, label, runner in workflow:
        steps.append(_run_step(step_id, label, runner, context))

    status = "pass" if all(step.status == "pass" for step in steps) else "fail"
    result = DemoDayResult(
        status=status,
        checkedAt=_utc_now(),
        databasePath=str(db_path),
        artifactsDir=str(artifacts),
        controlCenterRoute="#home",
        realPublishingEnabled=False,
        realReplySendingEnabled=False,
        realSocialApisEnabled=False,
        steps=steps,
    )
    if created_temp is not None:
        created_temp.cleanup()
    return result


def _run_step(
    step_id: str,
    label: str,
    runner: Callable[[DemoDayContext], list[str]],
    context: DemoDayContext,
) -> DemoDayStep:
    try:
        details = runner(context)
        return DemoDayStep(
            id=step_id,
            label=label,
            status="pass",
            summary=f"{label} passed.",
            details=details,
        )
    except Exception as error:  # pragma: no cover - defensive QA reporting
        return DemoDayStep(
            id=step_id,
            label=label,
            status="fail",
            summary=f"{label} failed.",
            details=[f"{type(error).__name__}: {error}"],
        )


def _step_onboarding(context: DemoDayContext) -> list[str]:
    state = context.app.dispatch(
        "POST",
        "/api/onboarding/complete",
        body={
            "brandProfile": {
                "businessName": "Demo Day Exterior Care",
                "industry": "Exterior cleaning",
                "description": "Safe fake setup for a local beta walkthrough.",
                "services": ["pressure washing", "gutter cleaning"],
                "serviceAreas": ["Demo City"],
                "brandVoice": "Helpful, plain-spoken, and local.",
                "commonCTAs": ["Request an estimate"],
            },
            "settings": {
                "defaultPlatformTargets": ["facebook", "instagram"],
                "requireApprovalBeforePublishing": True,
                "requireApprovalBeforeReplying": True,
                "emergencyPauseEnabled": False,
                "automationLevel": "approval_queue",
                "localDataDirectory": str(REPO_ROOT / "data"),
            },
        },
    ).body
    if state["status"] != "completed":
        raise AssertionError("Onboarding did not complete.")
    return ["Onboarding completed with approval-required safety defaults."]


def _step_media(context: DemoDayContext) -> list[str]:
    media = context.app.dispatch("GET", "/api/media").body
    if not media:
        raise AssertionError("No media assets found.")
    return [f"Media assets available: {len(media)}"]


def _step_generate(context: DemoDayContext) -> list[str]:
    bundle = context.app.dispatch(
        "POST",
        "/api/content-generation",
        body={
            "input": {
                "brandProfileId": DEMO_BRAND_ID,
                "contentGoal": "show_transformation",
                "contentAngle": "before_after",
                "selectedPlatforms": ["facebook"],
                "selectedMediaIds": ["demo-media-driveway-before"],
                "userInstructions": "Demo day local beta walkthrough.",
            },
            "options": {"providerName": "mock"},
        },
    ).body
    if bundle["generationProvider"] != "mock":
        raise AssertionError("Demo day generation did not use mock provider.")
    context.bundle = bundle
    return [f"Generated {len(bundle['posts'])} mock platform draft."]


def _step_drafts(context: DemoDayContext) -> list[str]:
    if not context.bundle:
        raise AssertionError("Generated bundle missing.")
    saved = context.app.dispatch(
        "POST",
        "/api/drafts/save-generated",
        body={
            "bundle": context.bundle,
            "save_request_id": "demo-day-check-save",
        },
    ).body
    draft_id = saved[0]["id"]
    approved = context.app.dispatch(
        "POST",
        f"/api/drafts/{draft_id}/approval",
        body={"action": "approve"},
    ).body
    if approved["approvalStatus"] != "approved":
        raise AssertionError("Draft was not approved locally.")
    context.draft_id = draft_id
    return [f"Draft saved and locally approved: {draft_id}"]


def _step_calendar(context: DemoDayContext) -> list[str]:
    if not context.draft_id:
        raise AssertionError("Draft ID missing.")
    scheduled = context.app.dispatch(
        "POST",
        f"/api/drafts/{context.draft_id}/schedule",
        body={
            "scheduled_for": "2027-06-11T15:00:00Z",
            "timezone": "America/New_York",
            "user_notes": "Demo day local schedule item.",
        },
    ).body
    context.scheduled_post_id = scheduled["id"]
    context.queue_item_id = scheduled["publishQueueItemId"]
    if scheduled["status"] != "scheduled":
        raise AssertionError("Scheduled post was not created.")
    return [f"Scheduled post: {scheduled['id']}", f"Queue item: {scheduled['publishQueueItemId']}"]


def _step_queue(context: DemoDayContext) -> list[str]:
    if not context.queue_item_id:
        raise AssertionError("Queue item ID missing.")
    preflight = context.app.dispatch(
        "POST",
        f"/api/publish-queue/{context.queue_item_id}/preflight",
        body={},
    ).body
    if not preflight.get("eligible", False):
        raise AssertionError("Queue item is not eligible for manual export.")
    return [
        f"Preflight status: {preflight.get('status', 'passed')}",
        "Manual export eligible; real publishing remains disabled.",
    ]


def _step_manual_export(context: DemoDayContext) -> list[str]:
    if not context.queue_item_id:
        raise AssertionError("Queue item ID missing.")
    export = context.app.dispatch(
        "POST",
        f"/api/publish-queue/{context.queue_item_id}/export-package",
        body={"copy_media": False},
    ).body
    marked = context.app.dispatch(
        "POST",
        f"/api/publish-queue/{context.queue_item_id}/mark-manually-exported",
        body={"notes": "Demo day manual export was checked locally."},
    ).body
    if marked["queueStatus"] != "manually_exported":
        raise AssertionError("Queue item was not marked manually exported.")
    return [f"Export package: {export['exportPath']}", "Marked manually exported locally."]


def _step_analytics(context: DemoDayContext) -> list[str]:
    snapshot = context.app.dispatch(
        "POST",
        "/api/analytics/snapshots",
        body={
            "brand_profile_id": DEMO_BRAND_ID,
            "platform": "facebook",
            "snapshot_date": "2027-06-12",
            "generated_post_id": context.draft_id,
            "scheduled_post_id": context.scheduled_post_id,
            "metrics": {
                "impressions": 180,
                "reach": 150,
                "views": 0,
                "likes": 8,
                "comments": 2,
                "shares": 1,
                "saves": 3,
                "clicks": 6,
                "leads": 1,
            },
            "notes": "Demo day manual metric entry.",
        },
    ).body
    if snapshot["source"] != "manual":
        raise AssertionError("Analytics snapshot was not marked manual.")
    return [f"Manual analytics snapshot: {snapshot['id']}"]


def _step_engagement(context: DemoDayContext) -> list[str]:
    result = context.app.dispatch(
        "POST",
        "/api/engagement/mock",
        body={"brand_profile_id": DEMO_BRAND_ID},
    ).body
    if result["createdCount"] + result["skippedCount"] < 8:
        raise AssertionError("Mock engagement did not create or preserve demo items.")
    return [f"Mock engagement created={result['createdCount']}, skipped={result['skippedCount']}"]


def _step_reply_suggestion(context: DemoDayContext) -> list[str]:
    suggestion = context.app.dispatch(
        "POST",
        f"/api/engagement/{context.engagement_item_id}/suggestions",
        body={},
    ).body
    approved = context.app.dispatch(
        "POST",
        f"/api/reply-suggestions/{suggestion['id']}/approve",
        body={"reason": "Demo day local approval only."},
    ).body
    if approved["status"] != "approved":
        raise AssertionError("Reply suggestion was not approved locally.")
    context.reply_suggestion_id = suggestion["id"]
    return [f"Reply suggestion approved locally: {suggestion['id']}", "No reply was sent."]


def _step_learning(context: DemoDayContext) -> list[str]:
    memory = context.app.dispatch(
        "POST",
        "/api/ai-memory/refresh",
        body={"brand_profile_id": DEMO_BRAND_ID},
    ).body
    report = context.app.dispatch(
        "POST",
        "/api/weekly-reports",
        body={
            "brand_profile_id": DEMO_BRAND_ID,
            "week_start_date": "2027-06-07",
            "source": "manual",
        },
    ).body
    if not report["recommendations"]:
        raise AssertionError("Weekly report did not include recommendations.")
    return [
        f"Memory created={memory['createdCount']}, updated={memory['updatedCount']}",
        f"Weekly report: {report['id']}",
    ]


def _step_backup(context: DemoDayContext) -> list[str]:
    backup = context.app.dispatch(
        "POST",
        "/api/backups",
        body={
            "backupType": "full_local_backup",
            "backupName": "demo-day-check",
            "includeMedia": False,
        },
    ).body
    if backup["includeSensitiveTokens"]:
        raise AssertionError("Backup included sensitive tokens.")
    return [f"Backup path: {backup['backupPath']}", "Sensitive tokens excluded."]


def _step_diagnostics(context: DemoDayContext) -> list[str]:
    diagnostics = context.app.dispatch("GET", "/api/diagnostics").body
    report = context.app.dispatch(
        "POST",
        "/api/diagnostics/export",
        body={"recentErrors": ["Demo day redaction check client_secret=hidden"]},
    ).body
    if "overallStatus" not in diagnostics:
        raise AssertionError("Diagnostics overall status missing.")
    return [f"Diagnostics status: {diagnostics['overallStatus']}", f"Report: {report['reportPath']}"]


def _step_safety(context: DemoDayContext) -> list[str]:
    health = context.app.dispatch("GET", "/api/health").body
    if health["realPublishing"] or health["realReplySending"]:
        raise AssertionError("Real publishing or real replies are unexpectedly enabled.")
    safety = context.app.dispatch("GET", "/api/safety-center").body
    if safety["publishingSafety"]["realPublishingEnabled"]:
        raise AssertionError("Safety Center reports real publishing enabled.")
    return [
        "realPublishing=false",
        "realReplySending=false",
        "Safety Center real publishing disabled.",
    ]


def _folder_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a deterministic local demo-day QA walkthrough. "
            "No real APIs are called and no real publishing/replies are sent."
        )
    )
    parser.add_argument("--database", help="SQLite database path to use.")
    parser.add_argument("--artifacts-dir", help="Directory for demo-day artifacts.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    result = run_demo_day_check(
        database_path=args.database,
        artifacts_dir=args.artifacts_dir,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_human_report(payload))
    return 1 if result.status == "fail" else 0


def _human_report(payload: dict[str, Any]) -> str:
    lines = [
        f"Demo day QA status: {payload['status']}",
        f"Checked at: {payload['checkedAt']}",
        f"Database: {payload['databasePath']}",
        f"Artifacts: {payload['artifactsDir']}",
        f"Control Center route: {payload['controlCenterRoute']}",
        "",
        "Safety:",
        f"- real_publishing={str(payload['realPublishingEnabled']).lower()}",
        f"- real_replies={str(payload['realReplySendingEnabled']).lower()}",
        f"- real_social_apis={str(payload['realSocialApisEnabled']).lower()}",
        "",
        "Steps:",
    ]
    for step in payload["steps"]:
        lines.append(f"- {step['label']}: {step['status']} - {step['summary']}")
        lines.extend(f"  - {detail}" for detail in step["details"])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
