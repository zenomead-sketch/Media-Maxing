PRAGMA foreign_keys = OFF;

ALTER TABLE app_settings RENAME TO app_settings_legacy_flags;

CREATE TABLE app_settings (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  automation_level TEXT NOT NULL DEFAULT 'approval_queue'
    CHECK (automation_level IN (
      'manual_assist',
      'approval_queue',
      'semi_auto_scheduling',
      'safe_auto_posting',
      'autonomous_content_engine'
    )),
  require_approval_before_publishing INTEGER NOT NULL DEFAULT 1,
  require_approval_before_replying INTEGER NOT NULL DEFAULT 1,
  emergency_pause_enabled INTEGER NOT NULL DEFAULT 0,
  kill_switch_enabled INTEGER NOT NULL DEFAULT 0,
  integrations_mode TEXT NOT NULL DEFAULT 'mock'
    CHECK (integrations_mode IN ('mock', 'disabled', 'real_oauth')),
  enable_real_network_calls INTEGER NOT NULL DEFAULT 0,
  enable_real_oauth INTEGER NOT NULL DEFAULT 0,
  enable_real_publishing INTEGER NOT NULL DEFAULT 0,
  token_storage_mode TEXT NOT NULL DEFAULT 'placeholder_not_stored'
    CHECK (token_storage_mode IN (
      'placeholder_not_stored',
      'keychain',
      'encrypted_file',
      'encrypted_database',
      'insecure_dev_only'
    )),
  settings_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

INSERT INTO app_settings (
  id,
  user_id,
  automation_level,
  require_approval_before_publishing,
  require_approval_before_replying,
  emergency_pause_enabled,
  kill_switch_enabled,
  integrations_mode,
  enable_real_network_calls,
  enable_real_oauth,
  enable_real_publishing,
  token_storage_mode,
  settings_json,
  created_at,
  updated_at
)
SELECT
  id,
  user_id,
  automation_level,
  require_approval_before_publishing,
  require_approval_before_replying,
  emergency_pause_enabled,
  kill_switch_enabled,
  CASE integrations_mode
    WHEN 'testing' THEN 'mock'
    WHEN 'real' THEN 'real_oauth'
    ELSE integrations_mode
  END,
  enable_real_network_calls,
  enable_real_oauth,
  enable_real_publishing,
  CASE token_storage_mode
    WHEN 'encrypted_local' THEN 'encrypted_file'
    WHEN 'development_insecure' THEN 'insecure_dev_only'
    ELSE token_storage_mode
  END,
  settings_json,
  created_at,
  updated_at
FROM app_settings_legacy_flags;

DROP TABLE app_settings_legacy_flags;

PRAGMA foreign_keys = ON;
