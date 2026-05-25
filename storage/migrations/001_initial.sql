CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    ts_utc TEXT NOT NULL,
    event_type TEXT NOT NULL,
    process_name TEXT NOT NULL,
    window_title TEXT,
    url TEXT,
    control_type TEXT,
    control_label TEXT,
    control_value TEXT,
    is_password INTEGER DEFAULT 0,
    semantic_label TEXT,
    redacted INTEGER DEFAULT 0,
    pii_flags TEXT,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts_utc);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_unenriched ON events(semantic_label)
    WHERE semantic_label IS NULL;

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    event_count INTEGER,
    apps_used TEXT,
    summary TEXT,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    status TEXT NOT NULL,
    task_name TEXT NOT NULL,
    description TEXT,
    frequency TEXT,
    estimated_minutes_per_run INTEGER,
    automation_confidence REAL,
    occurrence_count INTEGER,
    source_session_ids TEXT,
    definition_json TEXT NOT NULL,
    user_edits_json TEXT,
    hidden INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    deployed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    name TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    trigger_config_json TEXT,
    generated_script TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    trigger_context_json TEXT,
    log_text TEXT,
    error_message TEXT,
    minutes_saved INTEGER,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);

CREATE TABLE IF NOT EXISTS enrichment_cache (
    cache_key TEXT PRIMARY KEY,
    semantic_label TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    FOREIGN KEY (run_id) REFERENCES agent_runs(run_id)
);

CREATE TABLE IF NOT EXISTS rejected_fingerprints (
    fingerprint TEXT PRIMARY KEY,
    task_name TEXT,
    rejected_at TEXT NOT NULL
);
