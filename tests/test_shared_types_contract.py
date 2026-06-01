from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED_TYPES = REPO_ROOT / "packages" / "types" / "index.ts"


class SharedTypesContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.types = SHARED_TYPES.read_text(encoding="utf-8")

    def test_scheduling_and_publish_queue_contracts_are_exported(self):
        for declaration in (
            "export type ScheduledPostStatus",
            "export type PublishQueueStatus",
            "export type PreflightStatus",
            "export interface ScheduledPost",
            "export interface PublishQueueItem",
            "export interface PublishAttempt",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, self.types)
        for status in ("queued", "missed", "needs_attention", "manually_exported", "skipped"):
            with self.subTest(status=status):
                self.assertIn(f'"{status}"', self.types)

    def test_local_settings_and_connector_storage_contracts_are_exported(self):
        for declaration in (
            "export interface AppSettings",
            "export interface PlatformToken",
            "export interface OAuthState",
            "export interface ConnectorAuditLog",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, self.types)


if __name__ == "__main__":
    unittest.main()
