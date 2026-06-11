PRAGMA foreign_keys = OFF;

DROP INDEX IF EXISTS idx_ai_memory_brand_profile_id;

ALTER TABLE ai_memory RENAME TO ai_memory_learning_legacy;

CREATE TABLE ai_memory (
  id TEXT PRIMARY KEY,
  brand_profile_id TEXT,
  memory_type TEXT NOT NULL
    CHECK (memory_type IN (
      'brand_rule',
      'content_preference',
      'audience_learning',
      'platform_learning',
      'performance_learning',
      'safety_learning',
      'user_preference',
      'rejected_strategy',
      'approved_strategy'
    )),
  summary TEXT NOT NULL,
  title TEXT,
  content TEXT,
  confidence TEXT NOT NULL DEFAULT 'low'
    CHECK (confidence IN ('low', 'medium', 'high')),
  evidence_json TEXT NOT NULL DEFAULT '{}',
  source TEXT NOT NULL DEFAULT 'manual',
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'dismissed', 'archived', 'superseded')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (brand_profile_id) REFERENCES brand_profiles(id) ON DELETE SET NULL
);

INSERT INTO ai_memory (
  id,
  brand_profile_id,
  memory_type,
  summary,
  title,
  content,
  confidence,
  evidence_json,
  source,
  status,
  created_at,
  updated_at
)
SELECT
  id,
  brand_profile_id,
  memory_type,
  summary,
  title,
  content,
  confidence,
  evidence_json,
  source,
  status,
  created_at,
  updated_at
FROM ai_memory_learning_legacy;

DROP TABLE ai_memory_learning_legacy;

CREATE INDEX IF NOT EXISTS idx_ai_memory_brand_profile_id
  ON ai_memory(brand_profile_id);

CREATE INDEX IF NOT EXISTS idx_ai_memory_brand_status
  ON ai_memory(brand_profile_id, status);

ALTER TABLE weekly_reports
  ADD COLUMN underperforming_posts_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE weekly_reports
  ADD COLUMN engagement_summary_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE weekly_reports
  ADD COLUMN lead_signals_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE weekly_reports
  ADD COLUMN learning_updates_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE weekly_reports
  ADD COLUMN next_week_content_suggestions_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE weekly_reports
  ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE weekly_reports
  ADD COLUMN prompt_metadata_json TEXT NOT NULL DEFAULT '{}';

PRAGMA foreign_keys = ON;
