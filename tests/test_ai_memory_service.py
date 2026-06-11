from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.seed_demo import DEMO_BRAND_ID, seed_demo_database
from scripts.services.engagement import EngagementService
from scripts.services.ai_memory import AIMemoryService


class AIMemoryServiceTest(unittest.TestCase):
    def _database(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        db_path = Path(temp_dir.name) / "app.sqlite"
        seed_demo_database(db_path)
        return db_path

    def test_refresh_promotes_insights_and_approval_evidence_idempotently(self):
        db_path = self._database()
        service = AIMemoryService(db_path)

        first = service.refresh_from_local_evidence(brand_profile_id=DEMO_BRAND_ID)
        second = service.refresh_from_local_evidence(brand_profile_id=DEMO_BRAND_ID)

        self.assertGreaterEqual(first.createdCount, 2)
        self.assertEqual(second.createdCount, 0)
        self.assertEqual(second.updatedCount, len(second.memories))
        memories = service.list_memories(brand_profile_id=DEMO_BRAND_ID)
        self.assertTrue(any(memory.memoryType == "approved_strategy" for memory in memories))
        self.assertTrue(any(memory.memoryType == "performance_learning" for memory in memories))

    def test_mock_analytics_stay_labeled_mock_in_derived_memory(self):
        db_path = self._database()
        service = AIMemoryService(db_path)

        result = service.refresh_from_local_evidence(brand_profile_id=DEMO_BRAND_ID)

        mock_memories = [memory for memory in result.memories if memory.source == "mock"]
        self.assertGreaterEqual(len(mock_memories), 1)
        self.assertTrue(all(memory.evidence["demo"] for memory in mock_memories))
        self.assertTrue(
            any("mock" in memory.evidence["analyticsSources"] for memory in mock_memories)
        )

    def test_engagement_learning_stores_audit_ids_not_private_content(self):
        db_path = self._database()
        EngagementService(db_path).ingest_mock_engagement(brand_profile_id=DEMO_BRAND_ID)
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO reply_approvals (
                  id, engagement_item_id, action, previous_status,
                  new_status, reason, actor_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "test-reply-audit-escalate",
                    "mock-engagement-complaint",
                    "escalate",
                    "needs_reply",
                    "escalated",
                    "Owner review required.",
                    "test",
                    "2026-06-10T12:00:00Z",
                ),
            )
            connection.commit()

        memories = AIMemoryService(db_path).refresh_from_local_evidence(
            brand_profile_id=DEMO_BRAND_ID
        ).memories
        safety = next(
            memory
            for memory in memories
            if "replyApprovalIds" in memory.evidence
        )

        self.assertEqual(safety.evidence["replyApprovalIds"], ["test-reply-audit-escalate"])
        self.assertFalse(safety.evidence["privateEngagementContentStored"])
        self.assertNotIn("complaint", str(safety.evidence).lower())

    def test_manual_memory_can_be_archived_without_deletion(self):
        db_path = self._database()
        service = AIMemoryService(db_path)

        memory = service.create_manual_memory(
            brand_profile_id=DEMO_BRAND_ID,
            memory_type="user_preference",
            title="Prefer concise CTAs",
            content="Keep future CTA suggestions concise and owner-reviewed.",
        )
        archived = service.archive_memory(memory.id)

        self.assertEqual(archived.status, "archived")
        self.assertEqual(service.get_memory(memory.id).id, memory.id)

    def test_manual_memory_can_be_dismissed_without_deletion(self):
        db_path = self._database()
        service = AIMemoryService(db_path)

        memory = service.create_manual_memory(
            brand_profile_id=DEMO_BRAND_ID,
            memory_type="user_preference",
            title="Prefer concise educational posts",
            content="Test concise educational posts while keeping owner review required.",
        )
        dismissed = service.dismiss_memory(memory.id)

        self.assertEqual(dismissed.status, "dismissed")
        self.assertEqual(service.get_memory(memory.id).id, memory.id)
        self.assertNotIn(
            memory.id,
            [item.id for item in service.list_memories(brand_profile_id=DEMO_BRAND_ID)],
        )

    def test_cli_refresh_is_local_only(self):
        db_path = self._database()

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.services.ai_memory",
                "--database",
                str(db_path),
                "--brand-profile-id",
                DEMO_BRAND_ID,
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("external_ai_calls=false", result.stdout)
        self.assertIn("external_platform_calls=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
