from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.db.init_db import initialize_database, resolve_database_path
from scripts.services.ai_memory import AIMemoryRecord, AIMemoryRefreshResult, AIMemoryService
from scripts.services.analytics import AnalyticsService, ContentInsight
from scripts.services.weekly_reports import WeeklyReport, WeeklyReportService


class AILearningService:
    """Coordinate explainable, local-only learning and weekly reporting.

    This facade intentionally exposes no AI-provider or platform-network path.
    It turns stored local evidence into bounded memory that generation can use.
    """

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = initialize_database(resolve_database_path(database_path))
        self.analytics = AnalyticsService(self.database_path)
        self.memory = AIMemoryService(self.database_path)
        self.reports = WeeklyReportService(self.database_path)

    def generateContentInsights(
        self,
        *,
        brandProfileId: str,
        start: str | None = None,
        end: str | None = None,
        source: str | None = None,
    ) -> list[ContentInsight]:
        return self.analytics.create_content_insights(
            brand_profile_id=brandProfileId,
            start=start,
            end=end,
            source=source,
        )

    def updateLearningMemory(self, *, brandProfileId: str) -> AIMemoryRefreshResult:
        return self.memory.refresh_from_local_evidence(brand_profile_id=brandProfileId)

    def generateWeeklyReport(
        self,
        *,
        brandProfileId: str,
        weekStartDate: str,
        source: str | None = None,
    ) -> WeeklyReport:
        return self.reports.generate_report(
            brand_profile_id=brandProfileId,
            week_start_date=weekStartDate,
            source=source,
        )

    def getActiveLearningMemory(self, *, brandProfileId: str) -> list[AIMemoryRecord]:
        return self.memory.list_memories(
            brand_profile_id=brandProfileId,
            status="active",
        )

    def applyLearningToGenerationContext(
        self,
        *,
        brandProfileId: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        memories = self.getActiveLearningMemory(brandProfileId=brandProfileId)[
            : max(limit, 0)
        ]
        return {
            "activeAIMemory": [asdict(memory) for memory in memories],
            "learningMetadata": {
                "localOnly": True,
                "externalDataSent": False,
                "memoryCount": len(memories),
                "memoryLimit": max(limit, 0),
            },
        }

    def dismissMemory(self, memoryId: str) -> AIMemoryRecord:
        return self.memory.dismiss_memory(memoryId)

    def archiveMemory(self, memoryId: str) -> AIMemoryRecord:
        return self.memory.archive_memory(memoryId)

    # Snake-case aliases keep Python callers idiomatic while the public contract
    # stays easy to map into the browser/API layer.
    def generate_content_insights(self, **kwargs: Any) -> list[ContentInsight]:
        return self.generateContentInsights(**kwargs)

    def update_learning_memory(self, **kwargs: Any) -> AIMemoryRefreshResult:
        return self.updateLearningMemory(**kwargs)

    def generate_weekly_report(self, **kwargs: Any) -> WeeklyReport:
        return self.generateWeeklyReport(**kwargs)

    def get_active_learning_memory(self, **kwargs: Any) -> list[AIMemoryRecord]:
        return self.getActiveLearningMemory(**kwargs)

    def apply_learning_to_generation_context(self, **kwargs: Any) -> dict[str, Any]:
        return self.applyLearningToGenerationContext(**kwargs)

    def dismiss_memory(self, memory_id: str) -> AIMemoryRecord:
        return self.dismissMemory(memory_id)

    def archive_memory(self, memory_id: str) -> AIMemoryRecord:
        return self.archiveMemory(memory_id)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh local learning memory and generate an optional weekly report. "
            "No external APIs are called."
        )
    )
    parser.add_argument("--database", help="Path to the local SQLite database.")
    parser.add_argument("--brand-profile-id", required=True, help="Brand Brain ID.")
    parser.add_argument("--week-start-date", help="Optional ISO week start date.")
    args = parser.parse_args()

    service = AILearningService(args.database)
    refresh = service.updateLearningMemory(brandProfileId=args.brand_profile_id)
    output: dict[str, Any] = {"memoryRefresh": asdict(refresh)}
    if args.week_start_date:
        output["weeklyReport"] = asdict(
            service.generateWeeklyReport(
                brandProfileId=args.brand_profile_id,
                weekStartDate=args.week_start_date,
            )
        )
    print(json.dumps(output, sort_keys=True))
    print("external_ai_calls=false")
    print("external_platform_calls=false")
    print("local_only=true")


if __name__ == "__main__":
    main()
