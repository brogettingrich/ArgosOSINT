import sqlite3
import json
import uuid
import time
import random
from typing import List, Dict, Any, Optional
from app.config import DATABASE_PATH

def get_connection():
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def with_db_retry(func, max_retries=4):
    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.05 * (2 ** attempt) + random.uniform(0.01, 0.03))
            else:
                raise

def create_dossier(target_name: str, seed_username: str = "", seed_email: str = "", seed_phone: str = "") -> str:
    dossier_id = str(uuid.uuid4())
    def _op():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO dossiers (id, target_name, seed_username, seed_email, seed_phone)
            VALUES (?, ?, ?, ?, ?)
            """, (dossier_id, target_name, seed_username, seed_email, seed_phone))
            conn.commit()
            return dossier_id
        finally:
            conn.close()
    return with_db_retry(_op)

def update_dossier_ai_briefing(dossier_id: str, briefing_data: Dict[str, Any]):
    def _op():
        conn = get_connection()
        try:
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
        finally:
            conn.close()
    return with_db_retry(_op)

def save_scan_result(dossier_id: str, result: Dict[str, Any]):
    def _op():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            corrob = result.get("corroboration", {})
            meta = result.get("metadata", {})
            cursor.execute("""
            INSERT INTO scan_results (dossier_id, site, category, username, profile_url, found, status_code, latency_ms, corroboration_score, evidence, display_name, bio, avatar_url, avatar_hash, verified, is_seed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dossier_id,
                result.get("site", ""),
                result.get("category", "General"),
                result.get("username", ""),
                result.get("profile_url", ""),
                1 if result.get("found") else 0,
                result.get("status_code", 0),
                result.get("latency_ms", 0),
                corrob.get("score", 0),
                json.dumps(meta),
                meta.get("display_name"),
                meta.get("bio"),
                meta.get("avatar_url"),
                meta.get("avatar_hash"),
                1 if meta.get("is_verified") else 0,
                1 if result.get("is_seed") else 0
            ))
            conn.commit()
        finally:
            conn.close()
    return with_db_retry(_op)

def get_dossier_details(dossier_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, target_name, seed_username, seed_email, seed_phone, created_at, ai_briefing, confidence, inferred_identity, metadata_json FROM dossiers WHERE id = ?", (dossier_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute("SELECT site, category, username, profile_url, found, status_code, latency_ms, corroboration_score, evidence, display_name, bio, avatar_url, avatar_hash, verified, is_seed, created_at FROM scan_results WHERE dossier_id = ?", (dossier_id,))
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
                "display_name": r[9],
                "bio": r[10],
                "avatar_url": r[11],
                "avatar_hash": r[12],
                "verified": bool(r[13]),
                "is_seed": bool(r[14]),
                "created_at": r[15]
            })
        
        metadata = {}
        if row[9]:
            try:
                metadata = json.loads(row[9])
            except Exception:
                pass

        return {
            "id": row[0],
            "target_name": row[1],
            "seed_username": row[2],
            "seed_email": row[3],
            "seed_phone": row[4],
            "created_at": row[5],
            "ai_briefing": row[6],
            "confidence": row[7],
            "inferred_identity": row[8],
            "metadata": metadata,
            "results": results
        }
    finally:
        conn.close()

def get_all_dossiers() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT d.id, d.target_name, d.seed_username, d.seed_email, d.seed_phone, d.ai_briefing, d.confidence, d.created_at, COUNT(s.id) as found_count
        FROM dossiers d
        LEFT JOIN scan_results s ON d.id = s.dossier_id AND s.found = 1
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """)
        rows = cursor.fetchall()
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
                "findings_count": r[8]
            }
            for r in rows
        ]
    finally:
        conn.close()

def get_all_settings() -> Dict[str, str]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM app_settings")
        rows = cursor.fetchall()
        return {k: v for k, v in rows}
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default
    finally:
        conn.close()

def set_setting(key: str, value: str):
    def _op():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, value))
            conn.commit()
        finally:
            conn.close()
    return with_db_retry(_op)