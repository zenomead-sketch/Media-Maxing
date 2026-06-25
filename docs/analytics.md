# Analytics Foundation

The analytics foundation stores local performance history for approved content. It supports manual entry, clearly labeled mock/demo analytics, and a guarded Facebook/Instagram analytics sync through the local API companion when Meta credentials are configured.

The local manual/mock service is implemented in `scripts/services/analytics.py`. Guarded Meta sync lives in `scripts/services/meta_analytics.py`.

The static web shell includes an Analytics screen. When launched through the
localhost bridge, manual snapshots, mock snapshots, and insight status updates
persist to SQLite. Opening the HTML file directly uses a clearly labeled
temporary `localStorage` demo fallback. The Python service remains the SQLite
source of truth.

## Supported Sources

Every snapshot records its provenance:

- `manual`: entered by the user.
- `mock`: clearly fake demo data for development.
- `platform_api`: real platform data synced through a guarded server-side integration after the account, scopes, local token mode, and Meta API response all allow it. Today this is limited to Facebook and Instagram through Meta Graph API.
- `imported_csv`: imported from a user-selected local file.
- `estimated`: explicitly labeled estimate.

Mock and manual metrics must never be presented as live platform analytics.
`platform_api` rows should still be described as locally stored synced metrics, not as a cloud dashboard.

## Local Tables

- `analytics_snapshots`: point-in-time measurements for a post.
- `post_performance_metrics`: local aggregate totals and trend summaries.
- `analytics_imports`: safe audit records for manual, mock, CSV, or future API imports.
- `content_insights`: explainable observations with evidence and confidence.
- `ai_memory`: durable learning records with evidence and provenance.
- `weekly_reports`: local weekly summaries.

## Simple Rate Formulas

The MVP uses practical comparison formulas:

```text
engagementRate = (likes + comments + shares + saves) / max(reach or impressions or views, 1)
clickThroughRate = clicks / max(impressions or views or reach, 1)
leadRate = leads / max(clicks or impressions or views, 1)
performanceScore =
  engagementRate * 100 * 0.4
  + clickThroughRate * 100 * 0.2
  + leadRate * 100 * 0.3
  + min(saves, 10)
```

The performance score is capped at `100`. These formulas are intentionally simple. They are useful for local comparisons, but they are not universal platform definitions and should not be described as authoritative.

## Analytics Service

`AnalyticsService` supports:

- Creating and updating manual snapshots.
- Filtering snapshots by Brand Brain, platform, date range, and source.
- Generating deterministic fake demo metrics in development/demo mode or after an explicit request.
- Computing and storing per-post performance metrics.
- Computing dashboard totals and platform, content-angle, and content-goal breakdowns.
- Ranking top and underperforming posts.
- Creating simple rule-based content insights.
- Recording analytics import audits.

## Guarded Meta Analytics Sync

The Analytics screen includes **Sync Facebook / Instagram** when the local API bridge is available. The browser does not call Meta directly. It asks the local Python API to run `MetaAnalyticsService`, which can sync data only when local flags, connected accounts, scopes, token storage, and Meta API permissions are ready.

The service:

- verifies real OAuth and network flags are enabled;
- reads only connected Facebook or Instagram accounts from local SQLite;
- requires server-side account tokens that are available only in explicit local development token mode;
- attempts to fetch recent Facebook Page posts or Instagram media through Meta Graph API;
- stores a `published_posts` record for each external post;
- stores an `analytics_snapshots` row with `source = platform_api`;
- stores permalink, caption, posted time, metrics, and attached media references in `rawMetricsJson`;
- writes an `analytics_imports` audit row.

Required local flags for real Meta analytics sync:

```text
APP_ENV=development
ALLOW_INSECURE_TOKEN_STORAGE=true
INTEGRATIONS_MODE=real_oauth
ENABLE_REAL_OAUTH=true
ENABLE_REAL_NETWORK_CALLS=true
META_ENABLE_REAL_OAUTH=true
META_CLIENT_ID=...
META_CLIENT_SECRET=...
META_REDIRECT_URI=...
META_GRAPH_API_VERSION=v20.0
```

The sync expects connected accounts with analytics-related scopes:

- Facebook: `pages_show_list`, `pages_read_engagement`.
- Instagram: `instagram_basic`, `instagram_manage_insights`.

If an account is missing, expired, missing scopes, or missing a local server-side token, sync returns a safe error for that account. It does not expose tokens to the frontend.

Important local-token warning: this first real-use path currently relies on `ALLOW_INSECURE_TOKEN_STORAGE=true` with `APP_ENV=development`, matching the guarded Facebook posting path. That is acceptable for personal local testing only. Before broader real-user use, replace this with OS keychain or encrypted token storage.

The post detail panel on the Analytics screen can show synced Facebook/Instagram post media when Meta returns image URLs or thumbnails. Video media may appear as a link if only a media URL is available.

Snapshots are cumulative point-in-time measurements. When several snapshots exist for one post, summaries use the latest matching snapshot instead of adding every snapshot together. This avoids double-counting a post as its metrics grow over time.

Manual and mock snapshots with the same source, post links, and date are rejected or skipped. Mock generation never overwrites manual data.

## Mock Analytics

Mock generation is local-only and deterministic. It uses existing `published_posts` rows with `publish_mode = mock` or `manual_export`, plus completed local queue rows that do not yet have a matching published-post record.

Every generated row uses:

```text
source = mock
rawMetrics.demo = true
rawMetrics.realPlatformAnalytics = false
```

Mock generation is available by default only when app environment is `development`, `demo`, or `test`. A caller can explicitly request mock generation outside those modes for a deliberate demo workflow.

Run a local summary:

```text
python -m scripts.services.analytics --database data/app.sqlite
```

Generate clearly fake local demo metrics and summarize:

```text
python -m scripts.services.analytics --database data/app.sqlite --generate-mock
```

## AI Learning Safety

Learning records must include evidence and confidence. A low-confidence observation should remain a suggestion to test, not a business claim.

Confidence guidance:

- `low`: fewer than 5 relevant data points.
- `medium`: 5 to 20 relevant data points.
- `high`: more than 20 data points with a consistent pattern.

The app should not delete memory automatically. A user should be able to review, dismiss, archive, or supersede a learning record later.

`scripts/services/ai_memory.py` now promotes explainable insights and local review decisions into idempotent, evidence-backed memory. `scripts/services/weekly_reports.py` creates one deterministic local report per brand and week. See `docs/ai-learning-loop.md` and `docs/weekly-reports.md`.

The Analytics screen includes a **Weekly review and AI memory** panel. Through
the localhost bridge, the owner can generate a persisted weekly report,
refresh evidence-backed memory, review the summaries used in future draft
generation, and archive memory records locally.

## Demo Data

The seed script creates one clearly fake `mock` snapshot, one aggregate performance row, one mock import audit, one low-confidence content insight, one low-confidence AI memory record, and one `ai_mock` weekly report.

Initialize and seed a local database:

```text
python -m scripts.db.init_db --database data/app.sqlite
python -m scripts.db.seed_demo --database data/app.sqlite
```

## Not Built Yet

- CSV import parser.
- AI-provider insight generation.
- Automatic background analytics sync.
- Analytics sync for YouTube, TikTok, LinkedIn, X, or Threads.
- Production token storage for unattended analytics sync.

Real analytics sync remains opt-in and guarded. Real publishing and real reply sending are separate safety-gated features and are not enabled by the Analytics screen.
