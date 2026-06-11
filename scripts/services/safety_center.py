from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.db.init_db import REPO_ROOT, initialize_database, resolve_database_path
from scripts.db.settings import load_app_settings, update_app_settings


AUTOMATION_LEVELS = [
    "manual_assist",
    "approval_queue",
    "semi_auto_scheduling",
    "safe_auto_posting",
    "autonomous_content_engine",
]

CRITICAL_SAFETY_FLAGS = {
    "invented_testimonial",
    "fake_testimonial",
    "unsupported_guarantee",
    "approval_bypass_attempt",
    "emergency_pause_enabled",
    "missing_required_brand_claim_support",
    "private_customer_info_risk",
    "invented_price",
    "invented_availability",
    "aggressive_language",
    "privacy_risk",
    "complaint_mishandled",
}

BLOCKED_ACTIONS = [
    "scheduling_new_posts",
    "queue_readiness_changes",
    "mock_publishing",
    "manual_export_packages",
    "future_real_publishing",
    "future_real_reply_sending",
    "ai_auto_reply_actions",
    "automation_above_approval_queue",
]

ALLOWED_ACTIONS = [
    "viewing_existing_data",
    "editing_drafts",
    "editing_brand_brain",
    "importing_media",
    "creating_backups",
    "exporting_data_backup",
    "reading_analytics",
    "manual_status_notes",
]

KILL_SWITCH_ACTIONS = {
    "pause_all_automation": {
        "label": "Pause all automation",
        "confirmationPhrase": "PAUSE ALL",
        "description": "Enables emergency pause, locks automation to approval queue, and disables queue processing.",
    },
    "cancel_future_scheduled_posts": {
        "label": "Cancel all future scheduled posts",
        "confirmationPhrase": "CANCEL FUTURE POSTS",
        "description": "Cancels unprocessed scheduled posts and their queue items locally.",
    },
    "disable_queue_processing": {
        "label": "Disable all queue processing",
        "confirmationPhrase": "DISABLE QUEUE",
        "description": "Keeps queue items visible but prevents local runner readiness processing.",
    },
    "disconnect_accounts_locally": {
        "label": "Disconnect mock/connected accounts locally",
        "confirmationPhrase": "DISCONNECT ACCOUNTS",
        "description": "Marks local account metadata disconnected without contacting providers.",
    },
    "revoke_tokens_locally": {
        "label": "Mark tokens revoked locally",
        "confirmationPhrase": "REVOKE TOKENS",
        "description": "Marks token metadata revoked locally without provider API calls.",
    },
    "disable_ai_generation": {
        "label": "Disable AI generation temporarily",
        "confirmationPhrase": "DISABLE AI",
        "description": "Stores a local safety flag for UI/service checks.",
    },
    "export_safety_report": {
        "label": "Export safety report",
        "confirmationPhrase": "EXPORT SAFETY REPORT",
        "description": "Writes a local redacted safety status report.",
    },
    "full_local_reset_placeholder": {
        "label": "Full local reset placeholder",
        "confirmationPhrase": "RESET PLACEHOLDER",
        "description": "Does not delete data. Documents that destructive reset is not implemented.",
    },
}


class SafetyCenterError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


class SafetyCenterService:
    """Centralized local safety status, pause, and kill-switch service."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def get_state(self) -> dict[str, Any]:
        settings = load_app_settings(self.database_path)
        safety_flags = self._critical_safety_flags()
        pending = self._pending_approvals()
        queue = self._queue_summary()
        accounts = self._connected_account_summary()
        latest_pause = self._latest_pause_event()
        local_flags = self._local_safety_flags()

        return {
            "emergencyPause": {
                "enabled": settings.emergencyPauseEnabled,
                "enabledAt": latest_pause.get("createdAt") if settings.emergencyPauseEnabled else None,
                "enabledBy": latest_pause.get("actorType") if settings.emergencyPauseEnabled else None,
                "reason": latest_pause.get("details", {}).get("reason") if settings.emergencyPauseEnabled else None,
            },
            "automationLevel": settings.automationLevel,
            "automationLevels": [
                {
                    "id": level,
                    "label": level.replace("_", " "),
                    "current": level == settings.automationLevel,
                    "locked": level not in {"manual_assist", "approval_queue"},
                    "note": "Planned/locked in MVP; real autonomous publishing and replies remain disabled."
                    if level not in {"manual_assist", "approval_queue"}
                    else "Available local safety mode.",
                }
                for level in AUTOMATION_LEVELS
            ],
            "publishingSafety": {
                "realPublishingEnabled": False,
                "futureRealPublishingEligible": False,
                "status": "disabled_by_policy",
                "message": "Real publishing remains disabled in this build.",
            },
            "replySafety": {
                "realReplySendingEnabled": False,
                "approvalRequired": settings.requireApprovalBeforeReplying,
                "status": "local_approval_only",
                "message": "Replies are not sent automatically.",
            },
            "queueProcessing": {
                **queue,
                "disabled": bool(local_flags.get("queueProcessingDisabled", False)),
                "status": "paused" if settings.emergencyPauseEnabled else "local_only",
            },
            "connectedAccountSafety": accounts,
            "criticalSafetyFlags": safety_flags,
            "pendingApprovals": pending,
            "blockedActions": BLOCKED_ACTIONS,
            "allowedActions": ALLOWED_ACTIONS,
            "killSwitchActions": self.kill_switch_actions(),
            "auditLogs": self.list_audit_logs(limit=20),
            "localFlags": local_flags,
        }

    def set_emergency_pause(
        self,
        enabled: bool,
        *,
        actor_type: str = "user",
        reason: str | None = None,
    ) -> dict[str, Any]:
        self._require_actor_type(actor_type)
        current = load_app_settings(self.database_path)
        updates: dict[str, Any] = {"emergencyPauseEnabled": bool(enabled)}
        if enabled or current.automationLevel not in {"manual_assist", "approval_queue"}:
            updates["automationLevel"] = "approval_queue"
        update_app_settings(self.database_path, updates)
        self._append_audit_log(
            "emergency_pause_enabled" if enabled else "emergency_pause_disabled",
            actor_type=actor_type,
            details={
                "reason": _clean_text(reason),
                "previousEmergencyPauseEnabled": current.emergencyPauseEnabled,
                "newEmergencyPauseEnabled": bool(enabled),
                "previousAutomationLevel": current.automationLevel,
                "newAutomationLevel": updates.get("automationLevel", current.automationLevel),
            },
        )
        return self.get_state()

    def set_automation_level(
        self,
        level: str,
        *,
        actor_type: str = "user",
        reason: str | None = None,
    ) -> dict[str, Any]:
        self._require_actor_type(actor_type)
        if level not in AUTOMATION_LEVELS:
            raise SafetyCenterError("Unsupported automation level.", ["invalid_automation_level"])
        if level not in {"manual_assist", "approval_queue"}:
            raise SafetyCenterError(
                "Automation levels above approval_queue are planned/locked in the MVP.",
                ["automation_level_locked"],
            )
        current = load_app_settings(self.database_path)
        update_app_settings(self.database_path, {"automationLevel": level})
        self._append_audit_log(
            "automation_level_changed",
            actor_type=actor_type,
            details={
                "reason": _clean_text(reason),
                "previousAutomationLevel": current.automationLevel,
                "newAutomationLevel": level,
            },
        )
        return self.get_state()

    def run_kill_switch_action(
        self,
        action: str,
        *,
        actor_type: str = "user",
        confirmation_phrase: str | None = None,
    ) -> dict[str, Any]:
        self._require_actor_type(actor_type)
        config = KILL_SWITCH_ACTIONS.get(action)
        if config is None:
            raise SafetyCenterError("Unsupported kill switch action.", ["invalid_kill_switch_action"])
        if confirmation_phrase != config["confirmationPhrase"]:
            raise SafetyCenterError(
                f"Type {config['confirmationPhrase']!r} to confirm this action.",
                ["confirmation_phrase_required"],
            )

        self._append_audit_log(
            "kill_switch_action_started",
            actor_type=actor_type,
            details={"action": action, "label": config["label"]},
        )
        details: dict[str, Any]
        if action == "pause_all_automation":
            details = self._pause_all_automation(actor_type=actor_type)
        elif action == "cancel_future_scheduled_posts":
            details = self._cancel_unprocessed_schedule()
        elif action == "disable_queue_processing":
            details = self._set_local_safety_flag("queueProcessingDisabled", True)
            self._append_audit_log("queue_processing_disabled", actor_type=actor_type, details=details)
        elif action == "disconnect_accounts_locally":
            details = self._disconnect_accounts()
            self._append_audit_log("accounts_disconnected", actor_type=actor_type, details=details)
        elif action == "revoke_tokens_locally":
            details = self._revoke_tokens_locally()
            self._append_audit_log("tokens_marked_revoked", actor_type=actor_type, details=details)
        elif action == "disable_ai_generation":
            details = self._set_local_safety_flag("aiGenerationDisabled", True)
            self._append_audit_log("ai_generation_disabled", actor_type=actor_type, details=details)
        elif action == "export_safety_report":
            details = self._export_safety_report()
            self._append_audit_log("safety_report_exported", actor_type=actor_type, details=details)
        elif action == "full_local_reset_placeholder":
            details = {
                "destructiveResetImplemented": False,
                "message": "Full local reset is a placeholder. No data was deleted.",
            }
        else:  # pragma: no cover - guarded above
            raise SafetyCenterError("Unsupported kill switch action.", ["invalid_kill_switch_action"])

        self._append_audit_log(
            "kill_switch_action_completed",
            actor_type=actor_type,
            details={"action": action, **details},
        )
        return {"action": action, **details, **self.get_state()}

    def list_audit_logs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM safety_audit_logs
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [_audit_row_to_dict(row) for row in rows]

    def kill_switch_actions(self) -> list[dict[str, Any]]:
        return [{"id": action_id, **config} for action_id, config in KILL_SWITCH_ACTIONS.items()]

    def _pause_all_automation(self, *, actor_type: str) -> dict[str, Any]:
        self.set_emergency_pause(True, actor_type=actor_type, reason="Kill switch: pause all automation.")
        details = self._set_local_safety_flag("queueProcessingDisabled", True)
        self._append_audit_log("queue_processing_disabled", actor_type=actor_type, details=details)
        return {"paused": True, **details}

    def _cancel_unprocessed_schedule(self) -> dict[str, Any]:
        now = _now_utc()
        with closing(self._connection()) as connection:
            connection.execute("BEGIN")
            scheduled_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM scheduled_posts
                WHERE status IN ('scheduled', 'queued', 'missed', 'failed', 'needs_attention')
                """
            ).fetchone()[0]
            queue_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM publish_queue_items
                WHERE queue_status IN ('waiting', 'ready', 'blocked', 'failed')
                """
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE scheduled_posts
                SET status = 'canceled',
                    canceled_at = COALESCE(canceled_at, ?),
                    updated_at = ?
                WHERE status IN ('scheduled', 'queued', 'missed', 'failed', 'needs_attention')
                """,
                (now, now),
            )
            connection.execute(
                """
                UPDATE publish_queue_items
                SET queue_status = 'canceled',
                    updated_at = ?
                WHERE queue_status IN ('waiting', 'ready', 'blocked', 'failed')
                """,
                (now,),
            )
            connection.execute(
                """
                UPDATE generated_posts
                SET publish_readiness_status = 'canceled',
                    updated_at = ?
                WHERE id IN (
                  SELECT generated_post_id
                  FROM publish_queue_items
                  WHERE queue_status = 'canceled'
                )
                """,
                (now,),
            )
            connection.commit()
        details = {
            "scheduledPostsCanceled": int(scheduled_count),
            "queueItemsCanceled": int(queue_count),
        }
        self._append_audit_log("scheduled_posts_canceled", actor_type="system", details=details)
        return details

    def _disconnect_accounts(self) -> dict[str, Any]:
        now = _now_utc()
        with closing(self._connection()) as connection:
            account_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM social_accounts
                WHERE connection_status NOT IN ('disconnected', 'revoked')
                """
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE social_accounts
                SET connection_status = 'disconnected',
                    disconnected_at = COALESCE(disconnected_at, ?),
                    updated_at = ?
                WHERE connection_status NOT IN ('disconnected', 'revoked')
                """,
                (now, now),
            )
            connection.commit()
        return {"accountsDisconnected": int(account_count), "externalProviderCalled": False}

    def _revoke_tokens_locally(self) -> dict[str, Any]:
        now = _now_utc()
        with closing(self._connection()) as connection:
            token_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM platform_tokens
                WHERE revoked_at IS NULL
                """
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE platform_tokens
                SET revoked_at = ?,
                    updated_at = ?
                WHERE revoked_at IS NULL
                """,
                (now, now),
            )
            connection.commit()
        return {"tokensMarkedRevoked": int(token_count), "externalProviderCalled": False}

    def _export_safety_report(self) -> dict[str, Any]:
        state = self.get_state()
        data_dir = Path(load_app_settings(self.database_path).localDataDirectory).expanduser()
        if not data_dir.is_absolute():
            data_dir = (REPO_ROOT / data_dir).resolve()
        report_dir = data_dir / "exports" / "diagnostics"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"safety-report-{_stamp()}.json"
        report = {
            "generatedAt": _now_utc(),
            "localOnly": True,
            "realPublishingEnabled": False,
            "realReplySendingEnabled": False,
            "state": state,
        }
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return {"reportPath": str(report_path), "secretsIncluded": False}

    def _local_safety_flags(self) -> dict[str, Any]:
        with closing(self._connection()) as connection:
            row = connection.execute(
                "SELECT settings_json FROM app_settings WHERE id = 'default'"
            ).fetchone()
        raw = row[0] if row else "{}"
        settings_json = _decode_json(raw, {})
        safety_flags = settings_json.get("safetyCenter")
        return safety_flags if isinstance(safety_flags, dict) else {}

    def _set_local_safety_flag(self, key: str, value: Any) -> dict[str, Any]:
        now = _now_utc()
        with closing(self._connection()) as connection:
            row = connection.execute(
                "SELECT settings_json FROM app_settings WHERE id = 'default'"
            ).fetchone()
            settings_json = _decode_json(row[0] if row else "{}", {})
            safety_flags = settings_json.get("safetyCenter")
            if not isinstance(safety_flags, dict):
                safety_flags = {}
            safety_flags[key] = value
            safety_flags["updatedAt"] = now
            settings_json["safetyCenter"] = safety_flags
            connection.execute(
                """
                UPDATE app_settings
                SET settings_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 'default'
                """,
                (json.dumps(settings_json, sort_keys=True),),
            )
            connection.commit()
        return {"localFlags": safety_flags}

    def _critical_safety_flags(self) -> dict[str, Any]:
        rows: list[sqlite3.Row]
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT id, platform, headline, hook, safety_flags_json
                FROM generated_posts
                WHERE safety_flags_json IS NOT NULL
                """
            ).fetchall()
        counts: dict[str, int] = {}
        affected: list[dict[str, Any]] = []
        for row in rows:
            flags = _decode_json(row["safety_flags_json"], [])
            critical = [flag for flag in flags if flag in CRITICAL_SAFETY_FLAGS]
            if not critical:
                continue
            for flag in critical:
                counts[flag] = counts.get(flag, 0) + 1
            affected.append(
                {
                    "draftId": row["id"],
                    "platform": row["platform"],
                    "title": row["headline"] or row["hook"] or "Draft",
                    "flags": critical,
                }
            )
        return {"total": sum(counts.values()), "byFlag": counts, "affectedDrafts": affected[:10]}

    def _pending_approvals(self) -> dict[str, int]:
        with closing(self._connection()) as connection:
            drafts = _count(
                connection,
                "generated_posts",
                "approval_status IN ('needs_review', 'revision_requested')",
            )
            suggestions = _count(
                connection,
                "reply_suggestions",
                "status IN ('generated', 'edited')",
            )
            queue = _count(
                connection,
                "publish_queue_items",
                "queue_status IN ('waiting', 'blocked')",
            )
        return {
            "draftsNeedingReview": drafts,
            "replySuggestionsNeedingReview": suggestions,
            "queueItemsNeedingAttention": queue,
        }

    def _queue_summary(self) -> dict[str, Any]:
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT queue_status, COUNT(*)
                FROM publish_queue_items
                GROUP BY queue_status
                """
            ).fetchall()
        by_status = {row[0]: int(row[1]) for row in rows}
        return {"byStatus": by_status, "ready": by_status.get("ready", 0), "blocked": by_status.get("blocked", 0)}

    def _connected_account_summary(self) -> dict[str, Any]:
        with closing(self._connection()) as connection:
            rows = connection.execute(
                """
                SELECT connection_status, COUNT(*)
                FROM social_accounts
                GROUP BY connection_status
                """
            ).fetchall()
        by_status = {row[0]: int(row[1]) for row in rows}
        return {
            "byStatus": by_status,
            "connectedOrLimited": by_status.get("connected", 0) + by_status.get("limited", 0),
            "requiresReauth": by_status.get("requires_reauth", 0) + by_status.get("expired", 0),
            "tokensExposed": False,
        }

    def _latest_pause_event(self) -> dict[str, Any]:
        with closing(self._connection()) as connection:
            row = connection.execute(
                """
                SELECT *
                FROM safety_audit_logs
                WHERE action = 'emergency_pause_enabled'
                ORDER BY created_at DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        return _audit_row_to_dict(row) if row else {}

    def _append_audit_log(
        self,
        action: str,
        *,
        actor_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._require_actor_type(actor_type)
        with closing(self._connection()) as connection:
            connection.execute(
                """
                INSERT INTO safety_audit_logs (
                  id, action, actor_type, details_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    action,
                    actor_type,
                    json.dumps(details or {}, sort_keys=True),
                    _now_utc(),
                ),
            )
            connection.commit()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _require_actor_type(self, actor_type: str) -> None:
        if actor_type not in {"user", "system", "ai", "test"}:
            raise SafetyCenterError("Unsupported actor type.", ["invalid_actor_type"])


def _count(connection: sqlite3.Connection, table: str, where: str | None = None) -> int:
    query = f"SELECT COUNT(*) FROM {table}"
    if where:
        query = f"{query} WHERE {where}"
    return int(connection.execute(query).fetchone()[0])


def _audit_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "action": row["action"],
        "actorType": row["actor_type"],
        "details": _decode_json(row["details_json"], {}),
        "createdAt": row["created_at"],
    }


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _clean_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect local Safety Center state.")
    parser.add_argument("--database", help="Path to the SQLite database.")
    args = parser.parse_args()
    print(json.dumps(SafetyCenterService(args.database).get_state(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
