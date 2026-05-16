"""
Auth helpers: password hashing, Gmail validation, trial window, admin list.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

SALT = b"smorx-balloon-auth-v1"
ITERATIONS = 310_000
TRIAL_SECONDS_DEFAULT = 3 * 24 * 60 * 60  # 3 days


def hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), SALT, ITERATIONS).hex()


def verify_password(password: str, stored_hex: str) -> bool:
    try:
        return hmac.compare_digest(hash_password(password), stored_hex)
    except Exception:
        return False


def is_gmail(email: str) -> bool:
    e = (email or "").strip().lower()
    return e.endswith("@gmail.com") and "@" in e


def admin_emails() -> set[str]:
    raw = os.environ.get("BALLOON_ADMIN_EMAILS", "").strip()
    if not raw:
        return set()
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def trial_seconds() -> int:
    try:
        return int(os.environ.get("BALLOON_TRIAL_SECONDS", str(TRIAL_SECONDS_DEFAULT)))
    except ValueError:
        return TRIAL_SECONDS_DEFAULT


def is_admin_email(email: str) -> bool:
    return email.strip().lower() in admin_emails()


def trial_expired(user: dict) -> bool:
    if user.get("role") == "admin" or user.get("paid"):
        return False
    ts = user.get("trial_started_at")
    if ts is None:
        return False
    return (time.time() - float(ts)) > trial_seconds()


def trial_remaining_sec(user: dict) -> Optional[float]:
    if user.get("role") == "admin" or user.get("paid"):
        return None
    ts = user.get("trial_started_at")
    if ts is None:
        return float(trial_seconds())
    left = float(trial_seconds()) - (time.time() - float(ts))
    return max(0.0, left)
