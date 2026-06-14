PRAGMA foreign_keys = OFF;

CREATE TABLE generated_posts_real_publish (
  id TEXT PRIMARY KEY,
  content_idea_id TEXT,
  brand_profile_id TEXT NOT NULL,
  platform TEXT NOT NULL
    CHECK (platform IN ('facebook', 'instagram', 'threads', 'youtube', 'tiktok', 'linkedin', 'x')),
  caption TEXT NOT NULL,
  hashtags_json TEXT NOT NULL DEFAULT '[]',
  media_asset_ids_json TEXT NOT NULL DEFAULT '[]',
  approval_status TEXT NOT NULL DEFAULT 'needs_review'
    CHECK (approval_status IN (
      'draft',
      'needs_review',
      'approved',
      'rejected',
      'revision_requested',
      'archived'
    )),
  safety_flags_json TEXT NOT NULL DEFAULT '[]',
  generation_provider TEXT NOT NULL DEFAULT 'mock'
    CHECK (generation_provider IN ('mock', 'openai', 'anthropic', 'local')),
  prompt_metadata_json TEXT NOT NULL DEFAULT '{}',
  provider_metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  headline TEXT,
  hook TEXT,
  short_caption TEXT,
  long_caption TEXT,
  call_to_action TEXT,
  content_goal TEXT,
  content_angle TEXT,
  target_audience TEXT,
  campaign_name TEXT,
  offer_context TEXT,
  user_instructions TEXT,
  suggested_post_time TEXT,
  alt_text TEXT,
  notes TEXT,
  score_json TEXT NOT NULL DEFAULT '{}',
  prompt_template_id TEXT,
  prompt_version TEXT,
  generation_timestamp TEXT,
  last_scheduled_at TEXT,
  publish_readiness_status TEXT NOT NULL DEFAULT 'not_scheduled'
    CHECK (publish_readiness_status IN (
      'not_scheduled',
      'scheduled',
      'queued',
      'waiting',
      'ready',
      'blocked',
      'mock_published',
      'manually_exported',
      'platform_published',
      'failed',
      'canceled',
      'skipped'
    )),
  FOREIGN KEY (content_idea_id) REFERENCES content_ideas(id) ON DELETE SET NULL,
  FOREIGN KEY (brand_profile_id) REFERENCES brand_profiles(id) ON DELETE CASCADE
);

INSERT INTO generated_posts_real_publish (
  id, content_idea_id, brand_profile_id, platform, caption,
  hashtags_json, media_asset_ids_json, approval_status, safety_flags_json,
  generation_provider, prompt_metadata_json, provider_metadata_json,
  created_at, updated_at, headline, hook, short_caption, long_caption,
  call_to_action, content_goal, content_angle, target_audience,
  campaign_name, offer_context, user_instructions, suggested_post_time,
  alt_text, notes, score_json, prompt_template_id, prompt_version,
  generation_timestamp, last_scheduled_at, publish_readiness_status
)
SELECT
  id, content_idea_id, brand_profile_id, platform, caption,
  hashtags_json, media_asset_ids_json, approval_status, safety_flags_json,
  generation_provider, prompt_metadata_json, provider_metadata_json,
  created_at, updated_at, headline, hook, short_caption, long_caption,
  call_to_action, content_goal, content_angle, target_audience,
  campaign_name, offer_context, user_instructions, suggested_post_time,
  alt_text, notes, score_json, prompt_template_id, prompt_version,
  generation_timestamp, last_scheduled_at, publish_readiness_status
FROM generated_posts;

DROP TABLE generated_posts;
ALTER TABLE generated_posts_real_publish RENAME TO generated_posts;

CREATE INDEX IF NOT EXISTS idx_generated_posts_brand_profile_id
  ON generated_posts(brand_profile_id);

CREATE INDEX IF NOT EXISTS idx_generated_posts_approval_status
  ON generated_posts(approval_status);

CREATE TABLE publish_queue_items_real_publish (
  id TEXT PRIMARY KEY,
  scheduled_post_id TEXT NOT NULL,
  generated_post_id TEXT NOT NULL,
  brand_profile_id TEXT NOT NULL,
  platform TEXT NOT NULL
    CHECK (platform IN ('facebook', 'instagram', 'threads', 'youtube', 'tiktok', 'linkedin', 'x')),
  queue_status TEXT NOT NULL DEFAULT 'waiting'
    CHECK (queue_status IN (
      'waiting',
      'ready',
      'blocked',
      'processing',
      'mock_published',
      'manually_exported',
      'platform_published',
      'failed',
      'canceled',
      'skipped'
    )),
  due_at TEXT NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'America/New_York',
  priority INTEGER NOT NULL DEFAULT 100,
  preflight_status TEXT NOT NULL DEFAULT 'not_checked'
    CHECK (preflight_status IN ('not_checked', 'passed', 'warnings', 'errors', 'blocked')),
  preflight_errors_json TEXT NOT NULL DEFAULT '[]',
  preflight_warnings_json TEXT NOT NULL DEFAULT '[]',
  mock_publish_enabled INTEGER NOT NULL DEFAULT 0,
  manual_export_required INTEGER NOT NULL DEFAULT 1,
  last_checked_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (scheduled_post_id) REFERENCES scheduled_posts(id) ON DELETE CASCADE,
  FOREIGN KEY (generated_post_id) REFERENCES generated_posts(id) ON DELETE CASCADE,
  FOREIGN KEY (brand_profile_id) REFERENCES brand_profiles(id) ON DELETE CASCADE
);

INSERT INTO publish_queue_items_real_publish (
  id, scheduled_post_id, generated_post_id, brand_profile_id, platform,
  queue_status, due_at, timezone, priority, preflight_status,
  preflight_errors_json, preflight_warnings_json, mock_publish_enabled,
  manual_export_required, last_checked_at, created_at, updated_at
)
SELECT
  id, scheduled_post_id, generated_post_id, brand_profile_id, platform,
  queue_status, due_at, timezone, priority, preflight_status,
  preflight_errors_json, preflight_warnings_json, mock_publish_enabled,
  manual_export_required, last_checked_at, created_at, updated_at
FROM publish_queue_items;

DROP TABLE publish_queue_items;
ALTER TABLE publish_queue_items_real_publish RENAME TO publish_queue_items;

CREATE INDEX IF NOT EXISTS idx_publish_queue_items_status
  ON publish_queue_items(queue_status);

CREATE INDEX IF NOT EXISTS idx_publish_queue_items_due_at
  ON publish_queue_items(due_at);

CREATE INDEX IF NOT EXISTS idx_publish_queue_items_scheduled_post_id
  ON publish_queue_items(scheduled_post_id);

PRAGMA foreign_keys = ON;
