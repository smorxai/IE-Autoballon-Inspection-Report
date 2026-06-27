"""
Hardware fingerprint → stable Machine ID (e.g. 8F4A-91D2-CC77).

Combines several identifiers so a copied install folder will not run on
another PC:
  - Windows MachineGuid (registry, survives reinstalls of the app)
  - System drive volume serial number
  - Motherboard serial (best effort, via CIM/WMI)
  - CPU name (best effort)

All failures are tolerated — at least MachineGuid or volume serial is
always available on Windows.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys


def _machine_guid() -> str:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(val)
    except Exception:
        return ""


def _volume_serial(drive: str = "") -> str:
    """Volume serial number of the system drive (no admin rights needed)."""
    try:
        if not drive:
            drive = os.environ.get("SystemDrive", "C:") + "\\"
        serial = ctypes.c_uint32(0)
        ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(drive),
            None,
            0,
            ctypes.byref(serial),
            None,
            None,
            None,
            0,
        )
        return f"{serial.value:08X}"
    except Exception:
        return ""


def _cim_value(cim_class: str, prop: str) -> str:
    """Query a CIM/WMI property without showing a console window."""
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"(Get-CimInstance {cim_class}).{prop}",
        ]
        flags = 0x08000000  # CREATE_NO_WINDOW
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=flags if sys.platform == "win32" else 0,
        )
        return (out.stdout or "").strip().splitlines()[0].strip() if out.stdout else ""
    except Exception:
        return ""


def _raw_fingerprint() -> str:
    parts = [
        _machine_guid(),
        _volume_serial(),
        _cim_value("Win32_BaseBoard", "SerialNumber"),
        _cim_value("Win32_Processor", "Name"),
    ]
    raw = "|".join(p for p in parts if p)
    # Absolute last resort so we never bind to an empty string.
    return raw or (os.environ.get("COMPUTERNAME", "") + os.environ.get("USERNAME", ""))


def get_machine_id() -> str:
    """Stable Machine ID for this PC, formatted XXXX-XXXX-XXXX."""
    digest = hashlib.sha256(_raw_fingerprint().encode("utf-8", "ignore")).hexdigest().upper()
    return f"{digest[0:4]}-{digest[4:8]}-{digest[8:12]}"


if __name__ == "__main__":
    print("Machine ID:", get_machine_id())
