"""Auth feature flags and trial configuration."""
from __future__ import annotations

import os

from auth.database import IS_SQLITE


def balloon_auth_disabled() -> bool:
    """When true, API and pages work without login (local dev only)."""
    flag = os.environ.get("SMORX_DISABLE_BALLOON_AUTH", "").strip().lower()
    return flag in ("1", "true", "yes")


def database_configured() -> bool:
    """True when PostgreSQL URL is set or local SQLite fallback is active."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return True
    if url.startswith("sqlite:"):
        return True
    return IS_SQLITE


def auth_enabled() -> bool:
    """Auth is on when a database is available and dev bypass is not set."""
    if balloon_auth_disabled():
        return False
    return database_configured()


def trial_days() -> int:
    raw = os.environ.get("TRIAL_DAYS", "7").strip()
    try:
        n = int(raw)
        return max(1, min(n, 90))
    except ValueError:
        return 7


def trial_expired_message() -> str:
    d = trial_days()
    unit = "day" if d == 1 else "days"
    return f"Your {d}-{unit} free trial has expired. Please upgrade to continue."
