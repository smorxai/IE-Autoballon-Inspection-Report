"""
Trial login for SmorX.ai Auto Ballooning UI.

- Password is verified with PBKDF2-HMAC-SHA256 (never stored plaintext server-side for comparison).
- Default trial hash matches password test@123; override with SMORX_TRIAL_PASSWORD_HASH.
- Username defaults to Admin; override with SMORX_TRIAL_USER.
- Login rate limiting per client IP (in-memory; use Redis in multi-instance prod).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request

SALT = b"smorx-ai-trial-v1"
ITERATIONS = 310_000
# PBKDF2-SHA256 of "test@123" with SALT and ITERATIONS (hex)
_DEFAULT_TRIAL_PASSWORD_HASH = (
    "6289598f7514c1179326d0101804ad060ca0dc5e9cea635c15423b38ce088316"
)

_login_attempts: dict[str, list[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SEC = 15 * 60


def _hash_password(password: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), SALT, ITERATIONS
    ).hex()


def trial_username() -> str:
    return os.environ.get("SMORX_TRIAL_USER", "Admin").strip()


def trial_password_hash_expected() -> str:
    return os.environ.get("SMORX_TRIAL_PASSWORD_HASH", _DEFAULT_TRIAL_PASSWORD_HASH).strip()


def verify_credentials(username: str, password: str) -> bool:
    if not username or not password:
        return False
    if username.strip().casefold() != trial_username().casefold():
        return False
    return hmac.compare_digest(_hash_password(password), trial_password_hash_expected())


def check_login_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = _login_attempts[ip]
    window[:] = [t for t in window if now - t < LOGIN_WINDOW_SEC]
    if len(window) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Wait 15 minutes or try from another network.",
        )


def record_login_failure(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _login_attempts[ip].append(time.time())


def clear_login_attempts(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _login_attempts.pop(ip, None)


def session_secret() -> str:
    s = os.environ.get("SESSION_SECRET", "").strip()
    if len(s) >= 32:
        return s
    # Dev fallback — set SESSION_SECRET in production
    return "smorx-dev-change-me-set-session-secret-in-env-min-32-chars!!"


async def require_trial_api_auth(request: Request) -> None:
    # Dev only: allow scripts (e.g. Streamlit) to call API without browser session.
    # Never set in production.
    flag = os.environ.get("SMORX_DISABLE_AUTO_BALLOON_AUTH", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return
    if not request.session.get("trial_auth"):
        raise HTTPException(status_code=401, detail="Authentication required")
