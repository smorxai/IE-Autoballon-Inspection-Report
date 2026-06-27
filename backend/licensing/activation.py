"""
License key validation + encrypted, machine-bound activation file.

activation.dat (stored in %PROGRAMDATA%\SmorX\InspectionReport\):
  - JSON payload {machine_id, license_sha, created, version}
  - HMAC-SHA256 signed with APP_SECRET + machine_id
  - Fernet-encrypted with a key derived from APP_SECRET + machine_id

Because the encryption/signing key depends on the *current* PC's machine ID,
copying activation.dat (or the whole installed folder) to another PC makes
decryption fail → "License Invalid".
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from licensing.machine_id import get_machine_id

# Embedded secrets (also compiled/obfuscated in the shipped exe).
_APP_SECRET = b"SmorX-IRP-2026:ingenious#padma@8441$1564:do-not-share"
# SHA-256 of the official license key (the key itself is never stored).
_LICENSE_KEY_SHA256 = "5f2a4ada4e04acb6069800017f67c940e2a5d27c246ac2c80342c8b4dfb78ee5"

_ACTIVATION_VERSION = 1


def activation_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or os.path.expanduser("~")
    return Path(base) / "SmorX" / "InspectionReport"


def activation_path() -> Path:
    return activation_dir() / "activation.dat"


def validate_license_key(key: str) -> bool:
    """Constant-time check of the entered license key against the embedded hash."""
    entered = hashlib.sha256((key or "").strip().encode("utf-8")).hexdigest()
    return hmac.compare_digest(entered, _LICENSE_KEY_SHA256)


def _fernet_for_machine(machine_id: str):
    from cryptography.fernet import Fernet

    raw = hashlib.sha256(_APP_SECRET + machine_id.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(raw))


def _sign(payload: bytes, machine_id: str) -> str:
    return hmac.new(
        _APP_SECRET + machine_id.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()


def create_activation(license_key: str) -> tuple[bool, str]:
    """
    Validate the license key and write the machine-bound activation file.
    Returns (ok, message).
    """
    if not validate_license_key(license_key):
        return False, "Invalid license key."

    machine_id = get_machine_id()
    payload = json.dumps(
        {
            "version": _ACTIVATION_VERSION,
            "machine_id": machine_id,
            "license_sha": _LICENSE_KEY_SHA256,
            "created": int(time.time()),
        },
        separators=(",", ":"),
    ).encode("utf-8")

    blob = json.dumps(
        {"payload": payload.decode("utf-8"), "sig": _sign(payload, machine_id)},
        separators=(",", ":"),
    ).encode("utf-8")

    token = _fernet_for_machine(machine_id).encrypt(blob)
    try:
        activation_dir().mkdir(parents=True, exist_ok=True)
        activation_path().write_bytes(token)
    except Exception as exc:
        return False, f"Could not write activation file: {exc}"
    return True, f"Activated for Machine ID {machine_id}."


def check_activation() -> tuple[bool, str]:
    """
    Verify activation.dat exists, decrypts with THIS machine's key, has a valid
    signature, and is bound to THIS machine. Returns (ok, message).
    """
    p = activation_path()
    if not p.is_file():
        return False, "Not activated."

    machine_id = get_machine_id()
    try:
        blob = _fernet_for_machine(machine_id).decrypt(p.read_bytes())
    except Exception:
        # Wrong machine (copied folder) or tampered file.
        return False, "License invalid for this PC."

    try:
        data = json.loads(blob.decode("utf-8"))
        payload = data["payload"].encode("utf-8")
        sig = data["sig"]
    except Exception:
        return False, "Activation file corrupted."

    if not hmac.compare_digest(sig, _sign(payload, machine_id)):
        return False, "Activation signature mismatch."

    try:
        info = json.loads(payload.decode("utf-8"))
    except Exception:
        return False, "Activation file corrupted."

    if info.get("machine_id") != machine_id:
        return False, "License is bound to a different PC."
    if info.get("license_sha") != _LICENSE_KEY_SHA256:
        return False, "License key mismatch."
    return True, f"Licensed (Machine ID {machine_id})."


def deactivate() -> None:
    """Remove the local activation (for testing)."""
    try:
        activation_path().unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    ok, msg = check_activation()
    print("Machine ID:", get_machine_id())
    print("Status    :", "ACTIVATED" if ok else "NOT ACTIVATED", "-", msg)
