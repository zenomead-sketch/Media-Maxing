# Backup & Data

The Backup & Data screen creates local backups and exports. It does not upload anything to the cloud.

## Backup Types

- Full local backup: writes structured JSON exports, a sanitized SQLite database copy, safety report, and a manifest.
- Database-only backup: writes only a sanitized SQLite database copy and manifest.
- Content-only export: writes Brand Brain, media metadata, generated posts, schedules, queue data, and weekly reports.
- Brand Brain export: writes `brand-profiles.json`.
- Media metadata export: writes `media-assets.json`.
- Analytics export: writes `analytics.json` and `analytics.csv`.
- Engagement export: writes `engagement.json`.
- AI memory export: writes `ai-memory.json`.
- Safety report export: writes `safety-report.json` and `safety-report.md`.

## Folder Structure

Backups are written under:

```text
data/exports/backups/YYYY-MM-DD-HH-mm-backup-name/
```

A full backup can include:

```text
backup-manifest.json
README.md
app-settings.json
brand-profiles.json
media-assets.json
generated-posts.json
scheduled-posts.json
publish-queue.json
analytics.json
engagement.json
ai-memory.json
weekly-reports.json
connected-accounts.json
safety-report.json
database-backup.sqlite
media/                  optional
```

## Manifest

`backup-manifest.json` includes:

- backup ID
- creation time
- backup type
- whether media files were included
- whether sensitive tokens were included, always `false` in the MVP
- whether token metadata was included
- table counts
- file counts
- checksum placeholder notes
- warnings
- restore notes

Checksums are a planned hardening step and are recorded as not implemented for now.

## Secret Exclusion

Backups exclude by default:

- raw OAuth tokens
- encrypted token blobs
- refresh tokens
- access tokens
- authorization codes
- API keys
- client secrets
- bearer tokens
- raw provider responses containing credentials

The sanitized SQLite copy sets `platform_tokens.encrypted_access_token` and `platform_tokens.encrypted_refresh_token` to `NULL`.

The advanced token option only allows safe token metadata. It does not include raw token values.

## Media Files

Media metadata is exported by default.

If "include media" is selected, the service tries to copy linked local media files into a `media/` folder. Missing files are reported in the manifest warnings instead of failing the whole backup.

## Restore Support

Restore is preview-first in this MVP.

The restore preview:

- reads `backup-manifest.json`
- validates expected files exist
- shows backup type, file list, table counts, warnings, and restore plan
- confirms tokens will not be restored by default
- requires confirmation before any future destructive restore

Actual destructive restore is intentionally not automatic yet. A future restore implementation must create a pre-restore backup before overwriting current local data.

## Commands

Create a full local backup:

```powershell
python -m scripts.services.backup --database data/app.sqlite --type full_local_backup --name owner-safe-copy
```

Create a backup with media copies:

```powershell
python -m scripts.services.backup --database data/app.sqlite --type full_local_backup --name with-media --include-media
```

Export analytics:

```powershell
python -m scripts.services.backup --database data/app.sqlite --type analytics_export --name analytics-export
```

List backup history:

```powershell
python -m scripts.services.backup --database data/app.sqlite --list
```

Preview restore:

```powershell
python -m scripts.services.backup --database data/app.sqlite --preview-restore data/exports/backups/2026-06-10-12-00-owner-safe-copy
```

## Safety Notes

- Backups stay local.
- Restore preview does not change data.
- Full reset is not implemented.
- Real publishing and real replies remain disabled.
- Backups should not be committed to git.
