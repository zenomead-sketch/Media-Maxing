from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.db.analytics_models import WEEKLY_REPORT_GENERATORS
from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.services.analytics import AnalyticsService, PostPerformanceMetrics


class WeeklyReportServiceError(ValueError):
    def __init__(self, message: str, error_codes: list[str] | None = None):
        super().__init__(message)
        self.error_codes = error_codes or []


@dataclass(frozen=True)
class WeeklyReport:
    id: str
    brandProfileId: str
    weekStartDate: str
    weekEndDate: str
    summary: str
    wins: list[str]
    concerns: list[str]
    recommendations: list[str]
    topPosts: list[dict[str, Any]]
    platformBreakdown: dict[str, Any]
    metricTotals: dict[str, Any]
    generatedBy: str
    createdAt: str
    updatedAt: str


class WeeklyReportService:
    """Generate local weekly reports from analytics snapshots and insights."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))
        self.analytics = AnalyticsService(self.database_path)

    def generate_report(
        self,
        *,
        brand_profile_id: str,
        week_start_date: str,
        source: str | None = None,
    ) -> WeeklyReport:
        self._require_brand(brand_profile_id)
        week_start = _parse_date(week_start_date)
        week_end = week_start + timedelta(days=6)
        end_exclusive = week_start + timedelta(days=7)
        filters = {
            "brand_profile_id": brand_profile_id,
            "start": week_start.isoformat(),
            "end": end_exclusive.isoformat(),
            "source": source,
        }
        summary = self.analytics.compute_dashboard_summary(**filters)
        platform_rows = self.analytics.compute_platform_breakdown(**filters)
        top_posts = self.analytics.identify_top_posts(limit=5, **filters)
        insights = self.analytics.create_content_insights(
            brand_profile_id=brand_profile_id,
            start=week_start.isoformat(),
            end=end_exclusive.isoformat(),
            source=source,
        )
        sources = self._snapshot_sources(
            brand_profile_id=brand_profile_id,
            start=week_start.isoformat(),
            end=end_exclusive.isoformat(),
            source=source,
        )
        generated_by = "ai_mock" if sources and sources == {"mock"} else "system"
        wins = _wins(summary, top_posts)
        concerns = _concerns(summary, sources)
        recommendations = _recommendations(insights)
        metric_totals = {
            key: value
            for key, value in summary.items()
            if key != "topPost"
        }
        metric_totals["sources"] = sorted(sources)
        metric_totals["demo"] = generated_by == "ai_mock"
        platform_breakdown = {
            row["platform"]: row for row in platform_rows
        }
        report_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"local-social-ai-manager:weekly-report:{brand_profile_id}:{week_start.isoformat()}",
            )
        )
        now = _now_utc()
        with self._connection() as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO weekly_reports (
                      id, brand_profile_id, week_start_date, week_end_date,
                      summary, wins_json, concerns_json, recommendations_json,
                      top_posts_json, platform_breakdown_json,
                      metric_totals_json, generated_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                      summary = excluded.summary,
                      wins_json = excluded.wins_json,
                      concerns_json = excluded.concerns_json,
                      recommendations_json = excluded.recommendations_json,
                      top_posts_json = excluded.top_posts_json,
                      platform_breakdown_json = excluded.platform_breakdown_json,
                      metric_totals_json = excluded.metric_totals_json,
                      generated_by = excluded.generated_by,
                      updated_at = excluded.updated_at
                    """,
                    (
                        report_id,
                        brand_profile_id,
                        week_start.isoformat(),
                        week_end.isoformat(),
                        _summary_text(summary, sources),
                        _json(wins),
                        _json(concerns),
                        _json(recommendations),
                        _json([asdict(post) for post in top_posts]),
                        _json(platform_breakdown),
                        _json(metric_totals),
                        generated_by,
                        now,
                        now,
                    ),
                )
        return self.get_report(report_id)

    def get_report(self, report_id: str) -> WeeklyReport:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM weekly_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
        if not row:
            raise WeeklyReportServiceError(
                f"Weekly report {report_id!r} does not exist.",
                ["weekly_report_not_found"],
            )
        return _row_to_report(row)

    def list_reports(
        self,
        *,
        brand_profile_id: str | None = None,
    ) -> list[WeeklyReport]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM weekly_reports
                WHERE (? IS NULL OR brand_profile_id = ?)
                ORDER BY week_start_date DESC, created_at DESC
                """,
                (brand_profile_id, brand_profile_id),
            ).fetchall()
        return [_row_to_report(row) for row in rows]

    def _snapshot_sources(
        self,
        *,
        brand_profile_id: str,
        start: str,
        end: str,
        source: str | None,
    ) -> set[str]:
        snapshots = self.analytics.list_snapshots(
            brand_profile_id=brand_profile_id,
            start=start,
            end=end,
            source=source,
        )
        return {snapshot.source for snapshot in snapshots}

    def _require_brand(self, brand_profile_id: str) -> None:
        with self._connection() as connection:
            found = connection.execute(
                "SELECT 1 FROM brand_profiles WHERE id = ?",
                (brand_profile_id,),
            ).fetchone()
        if not found:
            raise WeeklyReportServiceError(
                f"Brand profile {brand_profile_id!r} does not exist.",
                ["brand_profile_not_found"],
            )

    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return closing(connection)


def _row_to_report(row: sqlite3.Row) -> WeeklyReport:
    return WeeklyReport(
        id=row["id"],
        brandProfileId=row["brand_profile_id"],
        weekStartDate=row["week_start_date"],
        weekEndDate=row["week_end_date"],
        summary=row["summary"],
        wins=_decode_json(row["wins_json"], []),
        concerns=_decode_json(row["concerns_json"], []),
        recommendations=_decode_json(row["recommendations_json"], []),
        topPosts=_decode_json(row["top_posts_json"], []),
        platformBreakdown=_decode_json(row["platform_breakdown_json"], {}),
        metricTotals=_decode_json(row["metric_totals_json"], {}),
        generatedBy=row["generated_by"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _wins(
    summary: dict[str, Any],
    top_posts: list[PostPerformanceMetrics],
) -> list[str]:
    wins: list[str] = []
    if summary["totalLeads"]:
        wins.append(f"{summary['totalLeads']} local lead signal(s) were recorded this week.")
    if top_posts:
        wins.append(
            f"The current top local post is on {top_posts[0].platform} "
            f"with comparison score {top_posts[0].performanceScore:.1f}."
        )
    return wins or ["No clear win is established yet. Keep collecting local metrics."]


def _concerns(summary: dict[str, Any], sources: set[str]) -> list[str]:
    concerns: list[str] = []
    if summary["totalPosts"] < 3:
        concerns.append("The sample is small. Treat patterns as ideas to test, not guarantees.")
    if "mock" in sources:
        concerns.append("This report includes clearly fake mock metrics for local demo use.")
    if not sources:
        concerns.append("No local analytics snapshots were found for this week.")
    return concerns


def _recommendations(insights: list[Any]) -> list[str]:
    values = [
        insight.recommendedAction
        for insight in insights
        if insight.recommendedAction
    ]
    return values[:4] or [
        "Add manual analytics after posting so future weekly comparisons use real local entries."
    ]


def _summary_text(summary: dict[str, Any], sources: set[str]) -> str:
    if not sources:
        return "No local analytics snapshots were recorded for this week."
    label = "Clearly fake mock" if sources == {"mock"} else "Local"
    return (
        f"{label} weekly summary: {summary['totalPosts']} post(s) tracked, "
        f"{summary['totalEngagements']} engagement signal(s), "
        f"{summary['totalClicks']} click(s), and {summary['totalLeads']} lead signal(s)."
    )


def _parse_date(raw_value: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except (TypeError, ValueError) as error:
        raise WeeklyReportServiceError(
            "week_start_date must be an ISO date such as 2026-06-08.",
            ["invalid_week_start_date"],
        ) from error


def _decode_json(raw_value: str | None, fallback: Any) -> Any:
    if not raw_value:
        return fallback
    try:
        decoded = json.loads(raw_value)
    except json.JSONDecodeError:
        return fallback
    return decoded if isinstance(decoded, type(fallback)) else fallback


def _json(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a local weekly performance report. No external APIs are called."
    )
    parser.add_argument("--database", help="Path to the local SQLite database.")
    parser.add_argument("--brand-profile-id", required=True, help="Brand Brain ID.")
    parser.add_argument("--week-start-date", required=True, help="ISO date for report start.")
    parser.add_argument("--source", help="Optional analytics source filter.")
    args = parser.parse_args()

    report = WeeklyReportService(args.database).generate_report(
        brand_profile_id=args.brand_profile_id,
        week_start_date=args.week_start_date,
        source=args.source,
    )
    print(json.dumps(asdict(report), sort_keys=True))
    print("external_platform_calls=false")


if __name__ == "__main__":
    main()
