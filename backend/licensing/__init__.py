"""
SmorX Inspection Report — licensing & machine binding.

Layers:
  1. Installer password           → installer/setup.iss (Inno Setup)
  2. License key activation       → activation.validate_license_key
  3. Machine binding              → machine_id.get_machine_id + activation.dat
  4. Compile/obfuscate            → build_exe.bat (PyInstaller / Nuitka)
  5. Encrypted activation file    → activation.dat is Fernet-encrypted + HMAC-signed
"""
from licensing.activation import (
    check_activation,
    create_activation,
    validate_license_key,
)
from licensing.machine_id import get_machine_id

__all__ = [
    "check_activation",
    "create_activation",
    "validate_license_key",
    "get_machine_id",
]
