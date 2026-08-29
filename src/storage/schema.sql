CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    triggered_at TEXT NOT NULL,
    trigger_metric TEXT NOT NULL,
    trigger_value REAL NOT NULL,
    diagnosis TEXT,
    tool_calls_json TEXT,
    action_proposed TEXT,
    action_approved INTEGER,
    action_taken TEXT,
    post_check_value REAL,
    diagnosis_correct INTEGER,
    resolved_at TEXT
);
