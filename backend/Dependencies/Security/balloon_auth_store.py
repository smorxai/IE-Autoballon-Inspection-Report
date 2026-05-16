"""
SQLite-backed user store for Auto Ballooning auth (no Mongo required).
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

_DB_PATH = Path(os.environ.get("BALLOON_AUTH_DB", "")).expanduser() if os.environ.get("BALLOON_AUTH_DB") else None


def _db_file() -> Path:
    if _DB_PATH:
        return _DB_PATH
    root = Path(__file__).resolve().parents[2]
    return root / ".Temp" / "balloon_auth.sqlite"


def _conn() -> sqlite3.Connection:
    path = _db_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS balloon_users (
                email TEXT PRIMARY KEY COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                paid INTEGER NOT NULL DEFAULT 0,
                trial_started_at REAL,
                created_at REAL NOT NULL
            )
            """
        )
        c.commit()


def get_user(email: str) -> Optional[dict[str, Any]]:
    init_db()
    with _conn() as c:
        row = c.execute(
            "SELECT email, password_hash, role, paid, trial_started_at, created_at FROM balloon_users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if not row:
        return None
    return {
        "email": row["email"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "paid": bool(row["paid"]),
        "trial_started_at": row["trial_started_at"],
        "created_at": row["created_at"],
    }


def create_user(email: str, password_hash: str, role: str = "user") -> None:
    init_db()
    now = time.time()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO balloon_users (email, password_hash, role, paid, trial_started_at, created_at)
            VALUES (?, ?, ?, 0, NULL, ?)
            """,
            (email.strip().lower(), password_hash, role, now),
        )
        c.commit()


def update_trial_start(email: str, ts: float) -> None:
    init_db()
    with _conn() as c:
        c.execute(
            "UPDATE balloon_users SET trial_started_at = ? WHERE email = ? AND trial_started_at IS NULL",
            (ts, email.strip().lower()),
        )
        c.commit()


def set_paid(email: str, paid: bool) -> int:
    init_db()
    with _conn() as c:
        cur = c.execute(
            "UPDATE balloon_users SET paid = ? WHERE email = ?",
            (1 if paid else 0, email.strip().lower()),
        )
        c.commit()
        return cur.rowcount


def list_users() -> list[dict[str, Any]]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT email, role, paid, trial_started_at, created_at FROM balloon_users ORDER BY created_at DESC"
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append({k: r[k] for k in r.keys()})
    return out
