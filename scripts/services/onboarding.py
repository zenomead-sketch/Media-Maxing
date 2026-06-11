from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.db.brand_profiles import (
    BrandProfile,
    create_brand_profile,
    list_brand_profiles,
    update_brand_profile,
)
from scripts.db.init_db import REPO_ROOT, initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings, update_app_settings


ONBOARDING_ID = "default"

ONBOARDING_STEP_IDS = [
    "welcome",
    "local_data",
    "brand_profile",
    "business_details",
    "services_areas",
    "platforms",
    "safety",
    "media",
    "demo_draft",
    "next_steps",
]

SETUP_CHECKLIST_ITEM_IDS = [
    "brand_profile_created",
    "local_data_ready",
    "safety_settings_confirmed",
    "media_added",
    "first_draft_generated",
    "first_draft_approved",
    "first_post_scheduled",
    "manual_export_tested",
    "analytics_added",
    "social_setup_reviewed",
]

STEP_LABELS = {
    "welcome": "Welcome",
    "local_data": "Local data directory",
    "brand_profile": "Create Brand Brain",
    "business_details": "Business details",
    "services_areas": "Services and service areas",
    "platforms": "Default platforms",
    "safety": "Safety settings",
    "media": "First media",
    "demo_draft": "First demo draft",
    "next_steps": "Review next steps",
}

CHECKLIST_LABELS = {
    "brand_profile_created": "Brand profile created",
    "local_data_ready": "Local data directory ready",
    "safety_settings_confirmed": "Safety settings confirmed",
    "media_added": "Media added",
    "first_draft_generated": "First draft generated",
    "first_draft_approved": "First draft approved",
    "first_post_scheduled": "First post scheduled",
    "manual_export_tested": "Manual export tested",
    "analytics_added": "Analytics demo or manual metrics added",
    "social_setup_reviewed": "Social accounts mock connected or setup reviewed",
}

CHECKLIST_OPTIONAL_IDS = {
    "media_added",
    "first_draft_generated",
    "manual_export_tested",
    "analytics_added",
    "social_setup_reviewed",
}

STATUS_VALUES = {"not_started", "in_progress", "completed", "skipped", "needs_attention"}


class OnboardingError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class OnboardingState:
    status: str
    currentStep: str
    completedSteps: list[str]
    skippedSteps: list[str]
    steps: list[dict[str, Any]]
    checklist: list[dict[str, Any]]
    checklistById: dict[str, dict[str, Any]]
    localDataDirectory: str
    localDataDirectoryExists: bool
    localDataDirectoryWritable: bool
    startedAt: str | None
    completedAt: str | None
    skippedAt: str | None
    createdAt: str
    updatedAt: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OnboardingService:
    """Local-first first-run setup state and checklist service."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def get_state(self) -> OnboardingState:
        with closing(self._connection()) as connection:
            row = self._ensure_row(connection)
        return self._state_from_row(row)

    def update_progress(
        self,
        *,
        current_step: str | None = None,
        completed_steps: list[str] | None = None,
        skipped_steps: list[str] | None = None,
        status: str | None = None,
    ) -> OnboardingState:
        if current_step is not None:
            self._require_step(current_step)
        cleaned_completed = self._clean_steps(completed_steps) if completed_steps is not None else None
        cleaned_skipped = self._clean_steps(skipped_steps) if skipped_steps is not None else None
        if status is not None and status not in {"not_started", "in_progress", "completed", "skipped"}:
            raise OnboardingError("Unsupported onboarding status.", ["invalid_onboarding_status"])

        with closing(self._connection()) as connection:
            current = self._ensure_row(connection)
            next_status = status or current["status"]
            if next_status == "not_started" and (cleaned_completed or cleaned_skipped):
                next_status = "in_progress"
            next_step = current_step or current["current_step"] or "welcome"
            next_completed = (
                cleaned_completed
                if cleaned_completed is not None
                else _decode_json(current["completed_steps_json"], [])
            )
            next_skipped = (
                cleaned_skipped
                if cleaned_skipped is not None
                else _decode_json(current["skipped_steps_json"], [])
            )
            now = _now_utc()
            connection.execute(
                """
                UPDATE onboarding_state
                SET status = ?,
                  current_step = ?,
                  completed_steps_json = ?,
                  skipped_steps_json = ?,
                  started_at = COALESCE(started_at, ?),
                  updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    next_step,
                    _json(next_completed),
                    _json(next_skipped),
                    now,
                    now,
                    ONBOARDING_ID,
                ),
            )
            connection.commit()
            row = self._require_row(connection)
        return self._state_from_row(row)

    def complete(self, payload: dict[str, Any] | None = None) -> OnboardingState:
        payload = payload or {}
        brand_payload = payload.get("brandProfile") or payload.get("brand_profile")
        settings_payload = payload.get("settings") or {}
        completed_steps = self._clean_steps(
            payload.get("completedSteps")
            or payload.get("completed_steps")
            or ONBOARDING_STEP_IDS
        )
        skipped_steps = self._clean_steps(
            payload.get("skippedSteps") or payload.get("skipped_steps") or []
        )

        if not isinstance(brand_payload, dict):
            raise OnboardingError(
                "Brand profile details are required to complete onboarding.",
                ["brand_profile_required"],
            )
        self._create_or_update_first_brand_profile(brand_payload)
        self._apply_safe_settings(settings_payload if isinstance(settings_payload, dict) else {})

        now = _now_utc()
        with closing(self._connection()) as connection:
            self._ensure_row(connection)
            connection.execute(
                """
                UPDATE onboarding_state
                SET status = 'completed',
                  current_step = 'next_steps',
                  completed_steps_json = ?,
                  skipped_steps_json = ?,
                  started_at = COALESCE(started_at, ?),
                  completed_at = ?,
                  skipped_at = NULL,
                  updated_at = ?
                WHERE id = ?
                """,
                (
                    _json(completed_steps),
                    _json(skipped_steps),
                    now,
                    now,
                    now,
                    ONBOARDING_ID,
                ),
            )
            connection.commit()
            row = self._require_row(connection)
        return self._state_from_row(row)

    def skip(self, *, reason: str | None = None) -> OnboardingState:
        now = _now_utc()
        overrides = {"skipReason": str(reason or "").strip()} if reason else {}
        with closing(self._connection()) as connection:
            self._ensure_row(connection)
            connection.execute(
                """
                UPDATE onboarding_state
                SET status = 'skipped',
                  current_step = 'next_steps',
                  checklist_overrides_json = ?,
                  skipped_at = ?,
                  updated_at = ?
                WHERE id = ?
                """,
                (_json(overrides), now, now, ONBOARDING_ID),
            )
            connection.commit()
            row = self._require_row(connection)
        return self._state_from_row(row)

    def restart(self) -> OnboardingState:
        now = _now_utc()
        with closing(self._connection()) as connection:
            self._ensure_row(connection)
            connection.execute(
                """
                UPDATE onboarding_state
                SET status = 'in_progress',
                  current_step = 'welcome',
                  completed_steps_json = '[]',
                  skipped_steps_json = '[]',
                  started_at = ?,
                  completed_at = NULL,
                  skipped_at = NULL,
                  updated_at = ?
                WHERE id = ?
                """,
                (now, now, ONBOARDING_ID),
            )
            connection.commit()
            row = self._require_row(connection)
        return self._state_from_row(row)

    def _create_or_update_first_brand_profile(self, payload: dict[str, Any]) -> BrandProfile:
        profiles = list_brand_profiles(self.database_path)
        if profiles:
            return update_brand_profile(
                self.database_path,
                profiles[0].id,
                self._clean_brand_payload(payload, partial=True),
            )
        return create_brand_profile(
            self.database_path,
            self._clean_brand_payload(payload, partial=False),
        )

    def _clean_brand_payload(self, payload: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        cleaned = dict(payload)
        if not partial or "businessName" in cleaned:
            business_name = cleaned.get("businessName")
            if not isinstance(business_name, str) or not business_name.strip():
                raise OnboardingError(
                    "Business name is required.",
                    ["business_name_required"],
                )
        return cleaned

    def _apply_safe_settings(self, settings_payload: dict[str, Any]) -> None:
        current = load_app_settings(self.database_path)
        updates = {
            "localDataDirectory": settings_payload.get(
                "localDataDirectory",
                current.localDataDirectory,
            ),
            "defaultPlatformTargets": settings_payload.get(
                "defaultPlatformTargets",
                current.defaultPlatformTargets,
            ),
            "automationLevel": "approval_queue",
            "requireApprovalBeforePublishing": True,
            "requireApprovalBeforeReplying": True,
            "emergencyPauseEnabled": False,
            "aiProviderPreference": settings_payload.get(
                "aiProviderPreference",
                current.aiProviderPreference,
            ),
        }
        update_app_settings(self.database_path, updates)

    def _state_from_row(self, row: sqlite3.Row) -> OnboardingState:
        completed_steps = self._clean_steps(_decode_json(row["completed_steps_json"], []))
        skipped_steps = self._clean_steps(_decode_json(row["skipped_steps_json"], []))
        settings = load_app_settings(self.database_path)
        data_dir = _resolve_local_data_dir(settings.localDataDirectory)
        data_dir_exists = data_dir.exists()
        data_dir_writable = _is_writable(data_dir)
        checklist = self._build_checklist(
            completed_steps=completed_steps,
            skipped_steps=skipped_steps,
            data_dir_exists=data_dir_exists,
            data_dir_writable=data_dir_writable,
        )
        checklist_by_id = {item["id"]: item for item in checklist}
        return OnboardingState(
            status=row["status"],
            currentStep=row["current_step"] or "welcome",
            completedSteps=completed_steps,
            skippedSteps=skipped_steps,
            steps=[
                {
                    "id": step_id,
                    "label": STEP_LABELS[step_id],
                    "status": _step_status(step_id, completed_steps, skipped_steps, row["current_step"]),
                }
                for step_id in ONBOARDING_STEP_IDS
            ],
            checklist=checklist,
            checklistById=checklist_by_id,
            localDataDirectory=settings.localDataDirectory,
            localDataDirectoryExists=data_dir_exists,
            localDataDirectoryWritable=data_dir_writable,
            startedAt=row["started_at"],
            completedAt=row["completed_at"],
            skippedAt=row["skipped_at"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )

    def _build_checklist(
        self,
        *,
        completed_steps: list[str],
        skipped_steps: list[str],
        data_dir_exists: bool,
        data_dir_writable: bool,
    ) -> list[dict[str, Any]]:
        counts = self._checklist_counts()
        statuses = {
            "brand_profile_created": "completed" if counts["brand_profiles"] else "not_started",
            "local_data_ready": "completed"
            if data_dir_exists and data_dir_writable
            else "needs_attention",
            "safety_settings_confirmed": "completed"
            if "safety" in completed_steps and self._safe_settings_confirmed()
            else "not_started",
            "media_added": "completed" if counts["media_assets"] else "not_started",
            "first_draft_generated": "completed" if counts["generated_posts"] else "not_started",
            "first_draft_approved": "completed" if counts["approved_posts"] else "not_started",
            "first_post_scheduled": "completed" if counts["scheduled_posts"] else "not_started",
            "manual_export_tested": "completed" if counts["manual_exports"] else "not_started",
            "analytics_added": "completed" if counts["analytics_snapshots"] else "not_started",
            "social_setup_reviewed": "completed" if counts["connected_accounts"] else "not_started",
        }
        if "media" in skipped_steps and statuses["media_added"] == "not_started":
            statuses["media_added"] = "skipped"
        if "demo_draft" in skipped_steps and statuses["first_draft_generated"] == "not_started":
            statuses["first_draft_generated"] = "skipped"

        return [
            {
                "id": item_id,
                "label": CHECKLIST_LABELS[item_id],
                "status": statuses[item_id],
                "optional": item_id in CHECKLIST_OPTIONAL_IDS,
            }
            for item_id in SETUP_CHECKLIST_ITEM_IDS
        ]

    def _checklist_counts(self) -> dict[str, int]:
        with closing(self._connection()) as connection:
            return {
                "brand_profiles": _count(connection, "brand_profiles"),
                "media_assets": _count(connection, "media_assets"),
                "generated_posts": _count(connection, "generated_posts"),
                "approved_posts": _count(
                    connection,
                    "generated_posts",
                    "approval_status = 'approved'",
                ),
                "scheduled_posts": _count(connection, "scheduled_posts"),
                "manual_exports": _count(
                    connection,
                    "publish_queue_items",
                    "queue_status = 'manually_exported'",
                ),
                "analytics_snapshots": _count(connection, "analytics_snapshots"),
                "connected_accounts": _count(
                    connection,
                    "social_accounts",
                    "connection_status IN ('connected', 'limited')",
                ),
            }

    def _safe_settings_confirmed(self) -> bool:
        settings = load_app_settings(self.database_path)
        return (
            settings.automationLevel == "approval_queue"
            and settings.requireApprovalBeforePublishing
            and settings.requireApprovalBeforeReplying
            and not settings.emergencyPauseEnabled
        )

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_row(self, connection: sqlite3.Connection) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM onboarding_state WHERE id = ?",
            (ONBOARDING_ID,),
        ).fetchone()
        if row is None:
            connection.execute(
                """
                INSERT INTO onboarding_state (
                  id, status, current_step, completed_steps_json,
                  skipped_steps_json, checklist_overrides_json
                ) VALUES (?, 'not_started', 'welcome', '[]', '[]', '{}')
                """,
                (ONBOARDING_ID,),
            )
            connection.commit()
            row = self._require_row(connection)
        return row

    def _require_row(self, connection: sqlite3.Connection) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM onboarding_state WHERE id = ?",
            (ONBOARDING_ID,),
        ).fetchone()
        if row is None:
            raise OnboardingError("Onboarding state was not initialized.", ["onboarding_state_missing"])
        return row

    def _clean_steps(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        for value in values:
            if value in ONBOARDING_STEP_IDS and value not in cleaned:
                cleaned.append(value)
        return cleaned

    def _require_step(self, step_id: str) -> None:
        if step_id not in ONBOARDING_STEP_IDS:
            raise OnboardingError("Unsupported onboarding step.", ["invalid_onboarding_step"])


def _count(connection: sqlite3.Connection, table: str, where: str | None = None) -> int:
    query = f"SELECT COUNT(*) FROM {table}"
    if where:
        query = f"{query} WHERE {where}"
    return int(connection.execute(query).fetchone()[0])


def _resolve_local_data_dir(raw_value: str) -> Path:
    data_dir = Path(raw_value or "./data").expanduser()
    if not data_dir.is_absolute():
        data_dir = (REPO_ROOT / data_dir).resolve()
    return data_dir


def _is_writable(path: Path) -> bool:
    if path.exists() and not path.is_dir():
        return False
    if path.exists():
        return os.access(path, os.W_OK)
    return os.access(path.parent if path.parent.exists() else REPO_ROOT, os.W_OK)


def _step_status(
    step_id: str,
    completed_steps: list[str],
    skipped_steps: list[str],
    current_step: str | None,
) -> str:
    if step_id in completed_steps:
        return "completed"
    if step_id in skipped_steps:
        return "skipped"
    if step_id == (current_step or "welcome"):
        return "in_progress"
    return "not_started"


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _now_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect or update local onboarding state.")
    parser.add_argument("--database", help="Path to the SQLite database.")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--skip", action="store_true")
    args = parser.parse_args()
    service = OnboardingService(args.database)
    if args.restart:
        state = service.restart()
    elif args.skip:
        state = service.skip(reason="Skipped from local CLI.")
    else:
        state = service.get_state()
    print(json.dumps(state.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
