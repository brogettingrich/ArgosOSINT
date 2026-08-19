import sqlite3
from app.config import DB_PATH

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dossiers (
        id TEXT PRIMARY KEY,
        target_name TEXT NOT NULL,
        seed_username TEXT,
        seed_email TEXT,
        seed_phone TEXT,
        ai_briefing TEXT,
        confidence INTEGER,
        inferred_identity TEXT,
        metadata_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dossier_id TEXT NOT NULL,
        site TEXT NOT NULL,
        username TEXT NOT NULL,
        category TEXT,
        profile_url TEXT,
        "exists" INTEGER DEFAULT 1,
        corroboration_score REAL,
        corroboration_verdict TEXT,
        found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dossier_id) REFERENCES dossiers (id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # Check and add new columns to dossiers if table already existed
    cursor.execute("PRAGMA table_info(dossiers)")
    cols = [col[1] for col in cursor.fetchall()]
    if "ai_briefing" not in cols:
        cursor.execute("ALTER TABLE dossiers ADD COLUMN ai_briefing TEXT")
    if "confidence" not in cols:
        cursor.execute("ALTER TABLE dossiers ADD COLUMN confidence INTEGER")
    if "inferred_identity" not in cols:
        cursor.execute("ALTER TABLE dossiers ADD COLUMN inferred_identity TEXT")
    if "metadata_json" not in cols:
        cursor.execute("ALTER TABLE dossiers ADD COLUMN metadata_json TEXT")

    conn.commit()
    conn.close()