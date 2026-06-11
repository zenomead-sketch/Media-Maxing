from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.db.analytics_models import (
    AI_MEMORY_CONFIDENCE_LEVELS,
    AI_MEMORY_STATUSES,
    AI_MEMORY_TYPES,
)
from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.services.analytics import AnalyticsService


class AIMemoryServiceError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class AIMemoryRecord:
    id: str
    brandProfileId: str | None
    memoryType: str
    title: str
    content: str
    summary: str
    confidence: str
    evidence: dict[str, Any]
    source: str
    status: str
    createdAt: str
    updatedAt: str


@dataclass(frozen=True)
class AIMemoryRefreshResult:
    createdCount: int
    updatedCount: int
    memories: list[AIMemoryRecord]


class AIMemoryService:
    """Create conservative local learning records from explainable evidence.

    The service stores references and counts, not private engagement content. It
    never calls an AI provider or platform API and never treats weak evidence as
    a guarantee.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))

    def create_manual_memory(
        self,
        *,
        brand_profile_id: str,
        memory_type: str,
        title: str,
        content: str,
        evidence: dict[str, Any] | None = None,
        confidence: str = "low",
    ) -> AIMemoryRecord:
        self._require_brand(brand_profile_id)
        _require_choice("memory_type", memory_type, AI_MEMORY_TYPES)
        _require_choice("confidence", confidence, AI_MEMORY_CONFIDENCE_LEVELS)
        return self._upsert_memory(
            key=f"manual:{uuid.uuid4()}",
            brand_profile_id=brand_profile_id,
            memory_type=memory_type,
            title=_require_text("title", title),
            content=_require_text("content", content),
            evidence=evidence or {"entryMode": "manual", "localOnly": True},
            confidence=confidence,
            source="manual",
        )[0]

    def refresh_from_local_evidence(
        self,
        *,
        brand_profile_id: str,
    ) -> AIMemoryRefreshResult:
        self._require_brand(brand_profile_id)
        AnalyticsService(self.database_path).create_content_insights(
            brand_profile_id=brand_profile_id
        )
        candidates = [
            *self._brand_rule_candidates(brand_profile_id),
            *self._insight_candidates(brand_profile_id),
            *self._performance_metric_candidates(brand_profile_id),
            *self._draft_review_candidates(brand_profile_id),
            *self._engagement_pattern_candidates(brand_profile_id),
            *self._engagement_review_candidates(brand_profile_id),
            *self._media_metadata_candidates(brand_profile_id),
        ]
        memories: list[AIMemoryRecord] = []
        created_count = 0
        updated_count = 0
        for candidate in candidates:
            memory, created = self._upsert_memory(
                brand_profile_id=brand_profile_id,
                **candidate,
            )
            memories.append(memory)
            if created:
                created_count += 1
            else:
                updated_count += 1
        return AIMemoryRefreshResult(
            createdCount=created_count,
            updatedCount=updated_count,
            memories=memories,
        )

    def list_memories(
        self,
        *,
        brand_profile_id: str | None = None,
        memory_type: str | None = None,
        status: str | None = "active",
        source: str | None = None,
    ) -> list[AIMemoryRecord]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if brand_profile_id:
            clauses.append("brand_profile_id = ?")
            parameters.append(brand_profile_id)
        if memory_type:
            _require_choice("memory_type", memory_type, AI_MEMORY_TYPES)
            clauses.append("memory_type = ?")
            parameters.append(memory_type)
        if status:
            _require_choice("status", status, AI_MEMORY_STATUSES)
            clauses.append("status = ?")
            parameters.append(status)
        if source:
            clauses.append("source = ?")
            parameters.append(source)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM ai_memory
                {"WHERE " + " AND ".join(clauses) if clauses else ""}
                ORDER BY updated_at DESC, created_at DESC, id ASC
                """,
                parameters,
            ).fetchall()
        return [_row_to_memory(row) for row in rows]

    def get_memory(self, memory_id: str) -> AIMemoryRecord:
        with self._connection() as connection:
            return _row_to_memory(self._require_memory(connection, memory_id))

    def archive_memory(self, memory_id: str) -> AIMemoryRecord:
        return self._update_memory_status(memory_id, "archived")

    def dismiss_memory(self, memory_id: str) -> AIMemoryRecord:
        return self._update_memory_status(memory_id, "dismissed")

    def _update_memory_status(self, memory_id: str, status: str) -> AIMemoryRecord:
        _require_choice("status", status, AI_MEMORY_STATUSES)
        now = _now_utc()
        with self._connection() as connection:
            self._require_memory(connection, memory_id)
            with connection:
                connection.execute(
                    """
                    UPDATE ai_memory
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, now, memory_id),
                )
        return self.get_memory(memory_id)

    def _brand_rule_candidates(self, brand_profile_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT services_json, blocked_phrases_json, supported_claims_json
                FROM brand_profiles
                WHERE id = ?
                """,
                (brand_profile_id,),
            ).fetchone()
        if not row:
            return []
        services = _decode_json(row["services_json"], [])
        blocked_phrases = _decode_json(row["blocked_phrases_json"], [])
        supported_claims = _decode_json(row["supported_claims_json"], [])
        return [
            {
                "key": "brand-brain:guardrails",
                "memory_type": "brand_rule",
                "title": "Brand Brain guardrails remain the source of truth",
                "content": (
                    "Use the saved local Brand Brain when drafting future content. "
                    "Respect blocked phrases and rely only on supported business claims."
                ),
                "evidence": {
                    "brandProfileIds": [brand_profile_id],
                    "serviceCount": len(services),
                    "blockedPhraseCount": len(blocked_phrases),
                    "supportedClaimCount": len(supported_claims),
                    "dataPoints": 1,
                    "localOnly": True,
                },
                "confidence": "low",
                "source": "local_learning",
            }
        ]

    def _insight_candidates(self, brand_profile_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM content_insights
                WHERE brand_profile_id = ? AND status = 'active'
                ORDER BY id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        type_map = {
            "best_content_type": "performance_learning",
            "best_platform": "platform_learning",
            "audience_signal": "audience_learning",
            "lead_signal": "audience_learning",
            "safety_signal": "safety_learning",
        }
        for row in rows:
            raw_evidence = _decode_json(row["evidence_json"], {})
            analytics_sources = self._analytics_sources_for_insight(row)
            source = (
                "mock"
                if raw_evidence.get("demo") or analytics_sources == {"mock"}
                else "local_learning"
            )
            data_points = int(
                raw_evidence.get("dataPoints", raw_evidence.get("data_points", 0))
            )
            candidates.append(
                {
                    "key": f"insight:{row['id']}",
                    "memory_type": type_map.get(row["insight_type"], "content_preference"),
                    "title": row["title"],
                    "content": _join_text(row["summary"], row["recommended_action"]),
                    "evidence": {
                        "contentInsightIds": [row["id"]],
                        "relatedPostIds": _decode_json(row["related_post_ids_json"], []),
                        "relatedMediaAssetIds": _decode_json(
                            row["related_media_asset_ids_json"], []
                        ),
                        "dataPoints": data_points,
                        "consistent": bool(raw_evidence.get("consistent", False)),
                        "analyticsSources": sorted(analytics_sources),
                        "demo": source == "mock",
                    },
                    "confidence": _confidence(
                        data_points,
                        consistent=bool(raw_evidence.get("consistent", False)),
                    ),
                    "source": source,
                }
            )
        return candidates

    def _performance_metric_candidates(
        self, brand_profile_id: str
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, platform, content_angle, media_asset_ids_json
                FROM post_performance_metrics
                WHERE brand_profile_id = ?
                ORDER BY performance_score DESC, id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
            source_rows = connection.execute(
                """
                SELECT DISTINCT source
                FROM analytics_snapshots
                WHERE brand_profile_id = ?
                """,
                (brand_profile_id,),
            ).fetchall()
        if not rows:
            return []
        platforms = _counts(row["platform"] for row in rows)
        content_angles = _counts((row["content_angle"] or "unknown") for row in rows)
        media_ids = sorted(
            {
                media_id
                for row in rows
                for media_id in _decode_json(row["media_asset_ids_json"], [])
            }
        )
        sources = {row["source"] for row in source_rows}
        data_points = len(rows)
        consistent = _has_clear_leader(platforms, data_points)
        return [
            {
                "key": "performance-metrics:summary",
                "memory_type": "performance_learning",
                "title": "Local post performance patterns are available for testing",
                "content": (
                    "Use the strongest locally measured platforms and content angles as "
                    "ideas to test again. Comparisons are evidence, not guarantees."
                ),
                "evidence": {
                    "postPerformanceMetricIds": [row["id"] for row in rows],
                    "relatedMediaAssetIds": media_ids,
                    "platformCounts": platforms,
                    "contentAngleCounts": content_angles,
                    "analyticsSources": sorted(sources),
                    "dataPoints": data_points,
                    "consistent": consistent,
                    "demo": sources == {"mock"},
                    "localOnly": True,
                },
                "confidence": _confidence(data_points, consistent=consistent),
                "source": "mock" if sources == {"mock"} else "local_learning",
            }
        ]

    def _analytics_sources_for_insight(self, insight: sqlite3.Row) -> set[str]:
        related_post_ids = _decode_json(insight["related_post_ids_json"], [])
        if not related_post_ids:
            return set()
        placeholders = ", ".join("?" for _ in related_post_ids)
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT source
                FROM analytics_snapshots
                WHERE published_post_id IN ({placeholders})
                   OR scheduled_post_id IN ({placeholders})
                   OR generated_post_id IN ({placeholders})
                """,
                (*related_post_ids, *related_post_ids, *related_post_ids),
            ).fetchall()
        return {row["source"] for row in rows}

    def _draft_review_candidates(self, brand_profile_id: str) -> list[dict[str, Any]]:
        groups = {
            "approved": (
                {"approved"},
                "approved_strategy",
                "Owner-approved drafts are available as strategy evidence",
                "Use approved drafts as local examples when proposing future content. "
                "Approval is evidence of owner preference, not proof of performance.",
            ),
            "revision": (
                {"rejected", "revision_requested", "edited_requires_reapproval"},
                "rejected_strategy",
                "Draft revisions are available as caution evidence",
                "Review rejected or revised drafts before repeating similar approaches. "
                "Keep the owner in control of future strategy changes.",
            ),
        }
        with self._connection() as connection:
            log_rows = connection.execute(
                """
                SELECT approval_logs.id, approval_logs.entity_id, approval_logs.action
                FROM approval_logs
                JOIN generated_posts
                  ON generated_posts.id = approval_logs.entity_id
                WHERE approval_logs.entity_type = 'generated_post'
                  AND generated_posts.brand_profile_id = ?
                ORDER BY approval_logs.created_at ASC, approval_logs.id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
            post_rows = connection.execute(
                """
                SELECT id, approval_status
                FROM generated_posts
                WHERE brand_profile_id = ?
                ORDER BY id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        for key, (actions, memory_type, title, content) in groups.items():
            matching_logs = [row["id"] for row in log_rows if row["action"] in actions]
            matching_posts = [
                row["id"] for row in post_rows if row["approval_status"] in actions
            ]
            data_points = len(set(matching_logs) | set(matching_posts))
            if data_points:
                candidates.append(
                    {
                        "key": f"draft-review:{key}",
                        "memory_type": memory_type,
                        "title": title,
                        "content": content,
                        "evidence": {
                            "approvalLogIds": matching_logs,
                            "generatedPostIds": matching_posts,
                            "dataPoints": data_points,
                            "localOnly": True,
                        },
                        "confidence": _confidence(data_points, consistent=True),
                        "source": "local_learning",
                    }
                )
        return candidates

    def _engagement_pattern_candidates(
        self, brand_profile_id: str
    ) -> list[dict[str, Any]]:
        groups = {
            "complaint": (
                {"complaint"},
                "safety_learning",
                "Complaint replies need empathetic owner escalation",
                "Acknowledge concerns calmly and escalate for owner review. "
                "Never auto-reply to complaints.",
            ),
            "pricing": (
                {"price_request"},
                "safety_learning",
                "Pricing questions should invite an estimate request",
                "Invite the person to request an estimate or message the business. "
                "Do not invent prices.",
            ),
            "lead": (
                {"booking_request", "urgent"},
                "audience_learning",
                "Lead questions need a clear human next step",
                "Use a concise helpful next step and keep a person in the loop. "
                "Do not invent scheduling availability.",
            ),
        }
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, intent, source
                FROM engagement_items
                WHERE brand_profile_id = ?
                ORDER BY received_at ASC, id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        for key, (intents, memory_type, title, content) in groups.items():
            matching = [row for row in rows if row["intent"] in intents]
            if not matching:
                continue
            sources = {row["source"] for row in matching}
            candidates.append(
                {
                    "key": f"engagement-pattern:{key}",
                    "memory_type": memory_type,
                    "title": title,
                    "content": content,
                    "evidence": {
                        "engagementItemIds": [row["id"] for row in matching],
                        "dataPoints": len(matching),
                        "privateEngagementContentStored": False,
                        "demo": sources == {"mock"},
                        "localOnly": True,
                    },
                    "confidence": _confidence(len(matching), consistent=True),
                    "source": "mock" if sources == {"mock"} else "local_learning",
                }
            )
        return candidates

    def _engagement_review_candidates(self, brand_profile_id: str) -> list[dict[str, Any]]:
        groups = {
            "approved": (
                {"approve", "mark_replied_manually"},
                "user_preference",
                "Reviewed engagement replies are available as owner preference evidence",
                "Use locally approved or manually handled replies as tone examples. "
                "Never send a future reply without owner approval.",
            ),
            "caution": (
                {"reject", "escalate", "mark_spam"},
                "safety_learning",
                "Engagement caution decisions should remain human-reviewed",
                "Keep escalation, rejected replies, and spam decisions under human review. "
                "Do not auto-reply to sensitive engagement.",
            ),
        }
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT reply_approvals.id, reply_approvals.action
                FROM reply_approvals
                JOIN engagement_items
                  ON engagement_items.id = reply_approvals.engagement_item_id
                WHERE engagement_items.brand_profile_id = ?
                ORDER BY reply_approvals.created_at ASC, reply_approvals.id ASC
                """,
                (brand_profile_id,),
            ).fetchall()
        candidates: list[dict[str, Any]] = []
        for key, (actions, memory_type, title, content) in groups.items():
            matching = [row["id"] for row in rows if row["action"] in actions]
            if matching:
                candidates.append(
                    {
                        "key": f"engagement-review:{key}",
                        "memory_type": memory_type,
                        "title": title,
                        "content": content,
                        "evidence": {
                            "replyApprovalIds": matching,
                            "dataPoints": len(matching),
                            "privateEngagementContentStored": False,
                            "localOnly": True,
                        },
                        "confidence": _confidence(len(matching), consistent=True),
                        "source": "local_learning",
                    }
                )
        return candidates

    def _media_metadata_candidates(self, brand_profile_id: str) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, job_context_json, metadata_json
                FROM media_assets
                ORDER BY id ASC
                """
            ).fetchall()
        reviewed: list[tuple[sqlite3.Row, dict[str, Any], dict[str, Any]]] = []
        for row in rows:
            job_context = _decode_json(row["job_context_json"], {})
            metadata = _decode_json(row["metadata_json"], {})
            if metadata.get("usageStatus") in {"reviewed", "ready_for_generation"}:
                reviewed.append((row, job_context, metadata))
        if not reviewed:
            return []
        content_angles = _counts(
            job_context.get("contentAngle", "unknown")
            for _, job_context, _ in reviewed
        )
        quality_values = [
            metadata.get("qualityRating")
            for _, _, metadata in reviewed
            if isinstance(metadata.get("qualityRating"), int)
        ]
        data_points = len(reviewed)
        consistent = _has_clear_leader(content_angles, data_points)
        return [
            {
                "key": "media-metadata:reviewed-assets",
                "memory_type": "content_preference",
                "title": "Reviewed media metadata can guide future draft context",
                "content": (
                    "Prefer locally reviewed media when proposing content. Use saved content "
                    "angles as context, then keep the owner in control of final selection."
                ),
                "evidence": {
                    "relatedMediaAssetIds": [row["id"] for row, _, _ in reviewed],
                    "contentAngleCounts": content_angles,
                    "averageQualityRating": (
                        round(sum(quality_values) / len(quality_values), 2)
                        if quality_values
                        else None
                    ),
                    "dataPoints": data_points,
                    "consistent": consistent,
                    "localOnly": True,
                },
                "confidence": _confidence(data_points, consistent=consistent),
                "source": "local_learning",
            }
        ]

    def _upsert_memory(
        self,
        *,
        key: str,
        brand_profile_id: str,
        memory_type: str,
        title: str,
        content: str,
        evidence: dict[str, Any],
        confidence: str,
        source: str,
    ) -> tuple[AIMemoryRecord, bool]:
        _require_choice("memory_type", memory_type, AI_MEMORY_TYPES)
        _require_choice("confidence", confidence, AI_MEMORY_CONFIDENCE_LEVELS)
        memory_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"local-social-ai-manager:memory:{brand_profile_id}:{key}",
            )
        )
        now = _now_utc()
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM ai_memory WHERE id = ?",
                (memory_id,),
            ).fetchone()
            with connection:
                connection.execute(
                    """
                    INSERT INTO ai_memory (
                      id, brand_profile_id, memory_type, title, content, summary,
                      confidence, evidence_json, source, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      memory_type = excluded.memory_type,
                      title = excluded.title,
                      content = excluded.content,
                      summary = excluded.summary,
                      confidence = excluded.confidence,
                      evidence_json = excluded.evidence_json,
                      source = excluded.source,
                      updated_at = excluded.updated_at
                    """,
                    (
                        memory_id,
                        brand_profile_id,
                        memory_type,
                        _require_text("title", title),
                        _require_text("content", content),
                        _require_text("content", content),
                        confidence,
                        _json(evidence),
                        _require_text("source", source),
                        now,
                        now,
                    ),
                )
        return self.get_memory(memory_id), not bool(exists)

    def _require_brand(self, brand_profile_id: str) -> None:
        with self._connection() as connection:
            found = connection.execute(
                "SELECT 1 FROM brand_profiles WHERE id = ?",
                (brand_profile_id,),
            ).fetchone()
        if not found:
            raise AIMemoryServiceError(
                f"Brand profile {brand_profile_id!r} does not exist.",
                ["brand_profile_not_found"],
            )

    @staticmethod
    def _require_memory(connection: sqlite3.Connection, memory_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM ai_memory WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if not row:
            raise AIMemoryServiceError(
                f"AI memory {memory_id!r} does not exist.",
                ["ai_memory_not_found"],
            )
        return row

    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)


def _row_to_memory(row: sqlite3.Row) -> AIMemoryRecord:
    return AIMemoryRecord(
        id=row["id"],
        brandProfileId=row["brand_profile_id"],
        memoryType=row["memory_type"],
        title=row["title"] or row["summary"],
        content=row["content"] or row["summary"],
        summary=row["summary"],
        confidence=row["confidence"],
        evidence=_decode_json(row["evidence_json"], {}),
        source=row["source"],
        status=row["status"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _confidence(data_points: int, *, consistent: bool = False) -> str:
    if data_points < 5:
        return "low"
    if data_points <= 20:
        return "medium"
    return "high" if consistent else "medium"


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        label = str(value or "unknown")
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _has_clear_leader(counts: dict[str, int], total: int) -> bool:
    return bool(total and counts and max(counts.values()) / total >= 0.7)


def _require_choice(field_name: str, value: str, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise AIMemoryServiceError(
            f"{field_name} must be one of: {', '.join(choices)}.",
            [f"invalid_{field_name}"],
        )


def _require_text(field_name: str, value: Any) -> str:
    cleaned = str(value).strip() if value is not None else ""
    if not cleaned:
        raise AIMemoryServiceError(
            f"{field_name} is required.",
            [f"invalid_{field_name}"],
        )
    return cleaned


def _join_text(summary: str, recommended_action: str | None) -> str:
    return (
        f"{summary} Recommended next step: {recommended_action}"
        if recommended_action
        else summary
    )


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh local evidence-backed AI memory. No external APIs are called."
    )
    parser.add_argument("--database", help="Path to the local SQLite database.")
    parser.add_argument("--brand-profile-id", required=True, help="Brand Brain ID.")
    args = parser.parse_args()

    result = AIMemoryService(args.database).refresh_from_local_evidence(
        brand_profile_id=args.brand_profile_id
    )
    print(json.dumps(asdict(result), sort_keys=True))
    print("external_ai_calls=false")
    print("external_platform_calls=false")


if __name__ == "__main__":
    main()
