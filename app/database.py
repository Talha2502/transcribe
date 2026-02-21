import sqlite3
import os
import threading
import json
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "storage/jobs.db")
_lock = threading.Lock()


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'queued',
            original_filename TEXT,
            audio_path TEXT,
            language TEXT,
            language_confidence REAL,
            duration_seconds REAL,
            full_text TEXT,
            segments TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_job(job_id, original_filename, audio_path):
    now = datetime.utcnow().isoformat()
    with _lock:
        conn = get_connection()
        conn.execute(
            """INSERT INTO jobs (id, status, original_filename, audio_path, created_at, updated_at)
               VALUES (?, 'queued', ?, ?, ?, ?)""",
            (job_id, original_filename, audio_path, now, now)
        )
        conn.commit()
        conn.close()
    return get_job(job_id)

def get_job(job_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    if not row:
        return None

    job = dict(row)
    if job.get("segments"):
        job["segments"] = json.loads(job["segments"])
    return job

def update_job(job_id, **kwargs):
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())

    with _lock:
        conn = get_connection()
        conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values + [job_id])
        conn.commit()
        conn.close()
    return get_job(job_id)

def get_all_jobs(status=None):
    conn = get_connection()
    if status:
        rows = conn.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_failed_jobs():
    return get_all_jobs(status="failed")


def delete_job(job_id):
    with _lock:
        conn = get_connection()
        cursor = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
    return deleted