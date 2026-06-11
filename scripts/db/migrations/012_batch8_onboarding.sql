CREATE TABLE IF NOT EXISTS onboarding_state (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'not_started'
    CHECK (status IN ('not_started', 'in_progress', 'completed', 'skipped')),
  current_step TEXT NOT NULL DEFAULT 'welcome',
  completed_steps_json TEXT NOT NULL DEFAULT '[]',
  skipped_steps_json TEXT NOT NULL DEFAULT '[]',
  checklist_overrides_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT,
  completed_at TEXT,
  skipped_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO onboarding_state (
  id,
  status,
  current_step,
  completed_steps_json,
  skipped_steps_json,
  checklist_overrides_json
) VALUES (
  'default',
  'not_started',
  'welcome',
  '[]',
  '[]',
  '{}'
);
