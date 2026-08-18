import sqlite3
import json
import uuid
from typing import Dict, Any, List, Optional
from app.config import DATABASE_PATH

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_dossier(target_name: str, seed_username: str = "", seed_email: str = "", seed_phone: str = "", notes: str = "") -> str:
    dossier_id = str(uuid.uuid4())[:8]
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO dossiers (id, target_name, seed_username, seed_email, seed_phone, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dossier_id, target_name, seed_username, seed_email, seed_phone, notes)
        )
        conn.commit()
        return dossier_id
    finally:
        conn.close()

def save_scan_result(dossier_id: str, item: Dict[str, Any]):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO scan_results (dossier_id, site, category, username, profile_url, found, status_code, latency_ms, corroboration_score, evidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dossier_id,
                item.get("site"),
                item.get("category"),
                item.get("username"),
                item.get("profile_url"),
                1 if item.get("found") else 0,
                item.get("status_code", 0),
                item.get("latency_ms", 0),
                item.get("corroboration", {}).get("score", 0),
                json.dumps(item.get("corroboration", {}).get("evidence", []))
            )
        )
        conn.commit()
    finally:
        conn.close()

def list_dossiers() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cur = conn.execute("""
            SELECT d.*, 
                   COUNT(CASE WHEN r.found = 1 THEN 1 END) as found_count,
                   COUNT(r.id) as total_scans
            FROM dossiers d
            LEFT JOIN scan_results r ON d.id = r.dossier_id
            GROUP BY d.id
            ORDER BY d.created_at DESC
        """)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def get_dossier_details(dossier_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        dossier_cur = conn.execute("SELECT * FROM dossiers WHERE id = ?", (dossier_id,))
        row = dossier_cur.fetchone()
        if not row:
            return None
        dossier = dict(row)

        results_cur = conn.execute(
            "SELECT * FROM scan_results WHERE dossier_id = ? AND found = 1 ORDER BY corroboration_score DESC", 
            (dossier_id,)
        )
        dossier["findings"] = [dict(r) for r in results_cur.fetchall()]
        return dossier
    finally:
        conn.close()