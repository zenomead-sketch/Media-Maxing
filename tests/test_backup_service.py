from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.db.init_db import initialize_database
from scripts.db.seed_demo import seed_demo_database
from scripts.db.settings import update_app_settings
from scripts.services.backup import BackupService, BackupServiceError


class BackupServiceTest(unittest.TestCase):
    def _database(self) -> tuple[tempfile.TemporaryDirectory, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        db_path = root / "app.sqlite"
        data_dir = root / "data"
        initialize_database(db_path)
        seed_demo_database(db_path)
        update_app_settings(db_path, {"localDataDirectory": str(data_dir)})
        return temp_dir, db_path, data_dir

    def _insert_sensitive_token(self, db_path: Path) -> None:
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                INSERT INTO platform_tokens (
                  id, social_account_id, platform, token_type,
                  encrypted_access_token, encrypted_refresh_token,
                  access_token_expires_at, refresh_token_expires_at,
                  scope, token_version, encryption_status,
                  last_refresh_at, revoked_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  encrypted_access_token = excluded.encrypted_access_token,
                  encrypted_refresh_token = excluded.encrypted_refresh_token
                """,
                (
                    "test-sensitive-token",
                    "demo-social-facebook-page",
                    "facebook",
                    "page_access",
                    "access_token_DO_NOT_EXPORT",
                    "refresh_token_DO_NOT_EXPORT",
                    "pages_manage_posts",
                    7,
                    "encrypted",
                    "2026-06-01T12:00:00Z",
                    "2026-06-01T12:00:00Z",
                ),
            )
            connection.commit()

    def test_full_backup_creates_manifest_json_and_sanitized_database_without_token_blobs(self):
        _, db_path, _ = self._database()
        self._insert_sensitive_token(db_path)

        result = BackupService(db_path).create_backup(
            backup_type="full_local_backup",
            backup_name="owner-safe-copy",
            include_media=False,
        )

        backup_path = Path(result["backupPath"])
        manifest = json.loads((backup_path / "backup-manifest.json").read_text())
        self.assertEqual(manifest["backupType"], "full_local_backup")
        self.assertFalse(manifest["includeMedia"])
        self.assertFalse(manifest["includeSensitiveTokens"])
        self.assertIn("generated_posts", manifest["tableCounts"])
        for file_name in [
            "app-settings.json",
            "brand-profiles.json",
            "media-assets.json",
            "generated-posts.json",
            "scheduled-posts.json",
            "publish-queue.json",
            "analytics.json",
            "engagement.json",
            "ai-memory.json",
            "weekly-reports.json",
            "safety-report.json",
            "database-backup.sqlite",
        ]:
            self.assertTrue((backup_path / file_name).exists(), file_name)

        all_text = "\n".join(
            path.read_text(errors="ignore")
            for path in backup_path.rglob("*")
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".txt", ".csv"}
        )
        self.assertNotIn("access_token_DO_NOT_EXPORT", all_text)
        self.assertNotIn("refresh_token_DO_NOT_EXPORT", all_text)

        with closing(sqlite3.connect(backup_path / "database-backup.sqlite")) as connection:
            row = connection.execute(
                """
                SELECT encrypted_access_token, encrypted_refresh_token
                FROM platform_tokens
                WHERE id = ?
                """,
                ("test-sensitive-token",),
            ).fetchone()
        self.assertEqual(row, (None, None))

    def test_specific_exports_and_restore_preview_are_safe(self):
        _, db_path, _ = self._database()
        service = BackupService(db_path)

        brand_export = service.create_backup(
            backup_type="brand_brain_export",
            backup_name="brand-only",
        )
        analytics_export = service.create_backup(
            backup_type="analytics_export",
            backup_name="analytics-only",
        )

        brand_path = Path(brand_export["backupPath"])
        analytics_path = Path(analytics_export["backupPath"])
        self.assertTrue((brand_path / "brand-profiles.json").exists())
        self.assertFalse((brand_path / "database-backup.sqlite").exists())
        self.assertTrue((analytics_path / "analytics.csv").exists())

        preview = service.preview_restore(brand_path)
        self.assertEqual(preview["status"], "ready")
        self.assertEqual(preview["backupType"], "brand_brain_export")
        self.assertFalse(preview["willRestoreTokens"])
        self.assertTrue(preview["requiresConfirmation"])

        invalid = brand_path.parent / "invalid-backup"
        invalid.mkdir()
        with self.assertRaises(BackupServiceError) as context:
            service.preview_restore(invalid)
        self.assertIn("manifest_missing", context.exception.error_codes)

    def test_include_media_copies_existing_local_media_files(self):
        _, db_path, data_dir = self._database()
        media_path = data_dir / "media" / "originals" / "demo-local-photo.jpg"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(b"fake image bytes")
        with closing(sqlite3.connect(db_path)) as connection:
            connection.execute(
                """
                UPDATE media_assets
                SET original_path = ?
                WHERE id = 'demo-media-driveway-before'
                """,
                (str(media_path),),
            )
            connection.commit()

        result = BackupService(db_path).create_backup(
            backup_type="full_local_backup",
            backup_name="with-media",
            include_media=True,
        )

        backup_path = Path(result["backupPath"])
        manifest = json.loads((backup_path / "backup-manifest.json").read_text())
        self.assertTrue(manifest["includeMedia"])
        self.assertGreaterEqual(manifest["fileCounts"]["mediaCopied"], 1)
        self.assertTrue(any((backup_path / "media").rglob("demo-local-photo.jpg")))


if __name__ == "__main__":
    unittest.main()
