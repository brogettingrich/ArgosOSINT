import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from app.config import DATABASE_PATH

def get_connection():
    return sqlite3.connect(str(DATABASE_PATH))

def create_dossier(target_name: str, seed_username: str = "", seed_email: str = "", seed_phone: str = "") -> str:
    dossier_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO dossiers (id, target_name, seed_username, seed_email, seed_phone)
    VALUES (?, ?, ?, ?, ?)
    """, (dossier_id, target_name, seed_username, seed_email, seed_phone))
    conn.commit()
    conn.close()
    return dossier_id

def update_dossier_ai_briefing(dossier_id: str, briefing_data: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE dossiers 
    SET ai_briefing = ?, confidence = ?, inferred_identity = ?, metadata_json = ?
    WHERE id = ?
    """, (
        briefing_data.get("briefing", ""),
        briefing_data.get("confidence", 0),
        briefing_data.get("inferred_identity") or (briefing_data.get("verified_identities", [None])[0]),
        json.dumps(briefing_data),
        dossier_id
    ))
    conn.commit()
    conn.close()

def save_scan_result(dossier_id: str, result: Dict[str, Any]):
    conn = get_connection()
    cursor = conn.cursor()
    corrob = result.get("corroboration", {})
    cursor.execute("""
    INSERT INTO scan_results (dossier_id, site, category, username, profile_url, found, status_code, latency_ms, corroboration_score, evidence)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dossier_id,
        result.get("site", ""),
        result.get("category", "General"),
        result.get("username", ""),
        result.get("profile_url", ""),
        1 if result.get("found") else 0,
        result.get("status_code", 200),
        result.get("latency_ms", 0),
        corrob.get("score", 50),
        json.dumps(result.get("evidence", {}))
    ))
    conn.commit()
    conn.close()

def get_dossier_details(dossier_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, target_name, seed_username, seed_email, seed_phone, notes, created_at, updated_at, ai_briefing, confidence, inferred_identity, metadata_json FROM dossiers WHERE id = ?", (dossier_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    cursor.execute("SELECT site, category, username, profile_url, found, status_code, latency_ms, corroboration_score, evidence, created_at FROM scan_results WHERE dossier_id = ?", (dossier_id,))
    results = []
    for r in cursor.fetchall():
        results.append({
            "site": r[0],
            "category": r[1],
            "username": r[2],
            "profile_url": r[3],
            "found": bool(r[4]),
            "status_code": r[5],
            "latency_ms": r[6],
            "corroboration": {"score": r[7]},
            "evidence": r[8],
            "created_at": r[9]
        })
    conn.close()
    
    metadata = {}
    if row[11]:
        try:
            metadata = json.loads(row[11])
        except Exception:
            pass

    return {
        "id": row[0],
        "target_name": row[1],
        "seed_username": row[2],
        "seed_email": row[3],
        "seed_phone": row[4],
        "created_at": row[6],
        "ai_briefing": row[8],
        "confidence": row[9],
        "inferred_identity": row[10],
        "metadata": metadata,
        "results": results
    }

def list_dossiers() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.id, d.target_name, d.seed_username, d.seed_email, d.seed_phone, d.ai_briefing, d.confidence, d.created_at, COUNT(s.id) as found_count
    FROM dossiers d
    LEFT JOIN scan_results s ON d.id = s.dossier_id AND s.found = 1
    GROUP BY d.id
    ORDER BY d.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "target_name": r[1],
            "seed_username": r[2],
            "seed_email": r[3],
            "seed_phone": r[4],
            "ai_briefing": r[5],
            "confidence": r[6],
            "created_at": r[7],
            "found_count": r[8]
        }
        for r in rows
    ]

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM app_settings")
    rows = cursor.fetchall()
    conn.close()
    return {k: v for k, v in rows}

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO app_settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))
    conn.commit()
    conn.close()