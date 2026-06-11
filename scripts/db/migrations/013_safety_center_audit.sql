CREATE TABLE IF NOT EXISTS safety_audit_logs (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL
    CHECK (action IN (
      'emergency_pause_enabled',
      'emergency_pause_disabled',
      'automation_level_changed',
      'kill_switch_action_started',
      'kill_switch_action_completed',
      'queue_processing_disabled',
      'accounts_disconnected',
      'tokens_marked_revoked',
      'scheduled_posts_canceled',
      'ai_generation_disabled',
      'safety_report_exported'
    )),
  actor_type TEXT NOT NULL DEFAULT 'user'
    CHECK (actor_type IN ('user', 'system', 'ai', 'test')),
  details_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_audit_logs_action
  ON safety_audit_logs(action);

CREATE INDEX IF NOT EXISTS idx_safety_audit_logs_created_at
  ON safety_audit_logs(created_at);
