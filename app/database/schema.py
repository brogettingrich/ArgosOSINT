import sqlite3
from app.config import DB_PATH


def _ensure_column(cursor, table: str, column: str, definition: str):
    """Add a column to a table if it does not already exist (idempotent migration)."""
    cols = {c[1] for c in cursor.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        pass
    try:
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    cursor = conn.cursor()

    # NOTE: column layout below MUST stay in sync with app/database/repository.py
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dossiers (
        id TEXT PRIMARY KEY,
        target_name TEXT NOT NULL,
        seed_username TEXT,
        seed_email TEXT,
        seed_phone TEXT,
        notes TEXT,
        ai_briefing TEXT,
        confidence INTEGER,
        inferred_identity TEXT,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dossier_id TEXT NOT NULL,
        site TEXT NOT NULL,
        category TEXT,
        username TEXT NOT NULL,
        profile_url TEXT,
        found INTEGER DEFAULT 0,
        status_code INTEGER,
        latency_ms INTEGER,
        corroboration_score REAL,
        evidence TEXT,
        display_name TEXT,
        bio TEXT,
        avatar_url TEXT,
        avatar_hash TEXT,
        verified INTEGER DEFAULT 0,
        is_seed INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dossier_id) REFERENCES dossiers (id)
    )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_dossier ON scan_results(dossier_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_results_found ON scan_results(found);")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # ---- dossiers migrations (idempotent for pre-existing databases) ----
    _ensure_column(cursor, "dossiers", "ai_briefing", "TEXT")
    _ensure_column(cursor, "dossiers", "confidence", "INTEGER")
    _ensure_column(cursor, "dossiers", "inferred_identity", "TEXT")
    _ensure_column(cursor, "dossiers", "metadata_json", "TEXT")
    _ensure_column(cursor, "dossiers", "notes", "TEXT")
    _ensure_column(cursor, "dossiers", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

    # ---- scan_results migrations ----
    _ensure_column(cursor, "scan_results", "category", "TEXT")
    _ensure_column(cursor, "scan_results", "found", "INTEGER DEFAULT 0")
    _ensure_column(cursor, "scan_results", "status_code", "INTEGER")
    _ensure_column(cursor, "scan_results", "latency_ms", "INTEGER")
    _ensure_column(cursor, "scan_results", "evidence", "TEXT")
    _ensure_column(cursor, "scan_results", "display_name", "TEXT")
    _ensure_column(cursor, "scan_results", "bio", "TEXT")
    _ensure_column(cursor, "scan_results", "avatar_url", "TEXT")
    _ensure_column(cursor, "scan_results", "avatar_hash", "TEXT")
    _ensure_column(cursor, "scan_results", "verified", "INTEGER DEFAULT 0")
    _ensure_column(cursor, "scan_results", "is_seed", "INTEGER DEFAULT 0")

    # ---- migrate legacy schema names so fresh installs and old DBs behave the same ----
    cols = {c[1] for c in cursor.execute("PRAGMA table_info(scan_results)")}
    if "exists" in cols and "found" not in cols:
        try:
            cursor.execute('ALTER TABLE scan_results RENAME COLUMN "exists" TO found')
        except Exception:
            pass
    if "corroboration_verdict" in cols and "evidence" not in cols:
        try:
            cursor.execute("ALTER TABLE scan_results RENAME COLUMN corroboration_verdict TO evidence")
        except Exception:
            pass

    conn.commit()
    conn.close()