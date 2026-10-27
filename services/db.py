"""Tiny SQLite storage. Only analysis RESULTS are stored - never the CV file."""
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import config


def _conn():
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                role TEXT,
                candidate TEXT,
                file_hash TEXT,
                result_json TEXT NOT NULL
            )"""
        )


def purge_expired():
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute("DELETE FROM analyses WHERE expires_at < ?", (now,))


def save_result(result, role, candidate, file_hash):
    rid = secrets.token_urlsafe(8)
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=config.RESULT_RETENTION_DAYS)
    with _conn() as c:
        c.execute(
            "INSERT INTO analyses VALUES (?,?,?,?,?,?,?)",
            (rid, now.isoformat(), exp.isoformat(), role, candidate, file_hash, json.dumps(result)),
        )
    return rid


def get_result(rid):
    with _conn() as c:
        row = c.execute("SELECT * FROM analyses WHERE id=?", (rid,)).fetchone()
    if not row:
        return None
    if row["expires_at"] < datetime.now(timezone.utc).isoformat():
        delete_result(rid)
        return None
    data = json.loads(row["result_json"])
    data["_meta"] = {
        "id": row["id"], "created_at": row["created_at"][:10], "role": row["role"],
        "candidate": row["candidate"], "expires_at": row["expires_at"][:10],
    }
    return data


def update_result(rid, result):
    with _conn() as c:
        c.execute("UPDATE analyses SET result_json=? WHERE id=?", (json.dumps(result), rid))


def find_by_hash(file_hash, role):
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM analyses WHERE file_hash=? AND role=? AND expires_at > ? ORDER BY created_at DESC LIMIT 1",
            (file_hash, role, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return row["id"] if row else None


def delete_result(rid):
    with _conn() as c:
        cur = c.execute("DELETE FROM analyses WHERE id=?", (rid,))
        return cur.rowcount > 0
