# SmorX Inspection Report — packaging & licensing

One password-protected `Setup.exe` you can carry on a pendrive. Installing asks a
password; first launch asks a license key; the license is bound to that PC so the
installed folder cannot be copied to another machine.

## The 5 protection layers

| Layer | What | Where |
|---|---|---|
| 1 | Installation password (also encrypts the packed files) | `installer/setup.iss` (`Password=` + `Encryption=yes`) |
| 2 | License key on first launch | `backend/licensing/activation.py` (`validate_license_key`) |
| 3 | Machine binding (disk serial, motherboard, MachineGuid → Machine ID) | `backend/licensing/machine_id.py` |
| 4 | Compiled exe instead of .py files | `installer/build_exe.bat` (PyInstaller; Nuitka alternative inside) |
| 5 | Encrypted + signed activation file | `activation.dat` (Fernet + HMAC, key derived from the Machine ID) |

- Install password: `Inspection_Moriya@2026_ingenious#padma@8441$1564`
- License key: `0RYP3BG2BB_0YZP9UXUPB_S2VEPN7L9C_XVZTXUZ5M0_DU3404QCL6_02LJD8WJ6K_770YD9T4W4_BU3JETSPXR`
  (only its SHA-256 hash is embedded in the code — the key itself is never stored)
- `activation.dat` lives in `%PROGRAMDATA%\SmorX\InspectionReport\`. It is encrypted
  with a key derived from the PC's Machine ID, so copying it (or the whole install
  folder) to another PC fails with "License invalid for this PC".

## Build steps (on your dev PC)

1. **Build the exe**

   ```bat
   installer\build_exe.bat
   ```

   Output: `backend\dist\SmorXInspectionReport\` (folder with `SmorXInspectionReport.exe`).
   Test it directly — first run shows the license key dialog.

2. **Build the installer** — install [Inno Setup 6](https://jrsoftware.org/isdl.php), then:

   ```bat
   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\setup.iss
   ```

   Output: `installer\Output\SmorX_InspectionReport_Setup.exe` → copy this single
   file to your pendrive.

## Install flow on the customer PC

```
Setup.exe → enter installation password → installs to
%LOCALAPPDATA%\SmorX Inspection Report → first launch → enter license key
→ Machine ID generated → encrypted activation.dat written → app opens in browser
```

Next launches: activation is checked silently and the app starts.

## Runtime configuration

`build_exe.bat` copies `backend\.env` next to the exe if present. The installed app
needs it for `DATABASE_URL` (Neon), `ANTHROPIC_API_KEY`, etc. If the customer PC
must work fully offline, leave `DATABASE_URL` unset (local SQLite is used) and use
`BALLOON_OCR_ENGINE=tesseract`.

## Honest notes

- PyInstaller ships bytecode; Nuitka (optional command in `build_exe.bat`) compiles
  to C for stronger obfuscation but takes much longer to build with torch installed.
- No client-side licensing is uncrackable; these layers stop copying/sharing by
  normal users, which is the stated goal.
- To change the license key later: compute `sha256` of the new key and replace
  `_LICENSE_KEY_SHA256` in `backend/licensing/activation.py`, then rebuild.
- To change the install password: edit `Password=` in `installer/setup.iss`, rebuild
  the installer.

## Testing machine binding without a second PC

```bat
python backend\licensing\machine_id.py     # shows this PC's Machine ID
python backend\licensing\activation.py    # shows activation status
```

Delete `%PROGRAMDATA%\SmorX\InspectionReport\activation.dat` to re-test first launch.
