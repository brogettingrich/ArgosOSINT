import sqlite3
from app.config import DATABASE_PATH

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS dossiers (
    id TEXT PRIMARY KEY,
    target_name TEXT NOT NULL,
    seed_username TEXT,
    seed_email TEXT,
    seed_phone TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dossier_id TEXT,
    site TEXT NOT NULL,
    category TEXT,
    username TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    found INTEGER NOT NULL,
    status_code INTEGER,
    latency_ms INTEGER,
    corroboration_score INTEGER DEFAULT 0,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(dossier_id) REFERENCES dossiers(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scan_dossier ON scan_results(dossier_id);
CREATE INDEX IF NOT EXISTS idx_scan_found ON scan_results(found);
"""

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()