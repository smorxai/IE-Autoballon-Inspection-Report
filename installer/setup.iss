; ============================================================
;  SmorX Inspection Report - password-protected installer
;  Layer 1: installation password (also encrypts packed files)
;
;  Build:  open this file in Inno Setup 6 (free) and press F9,
;          or:  ISCC.exe installer\setup.iss
;  Input:  backend\dist\SmorXInspectionReport\  (from build_exe.bat)
;  Output: installer\Output\SmorX_InspectionReport_Setup.exe
; ============================================================

#define MyAppName "SmorX Inspection Report"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SmorX.ai"
#define MyAppExeName "SmorXInspectionReport.exe"

[Setup]
AppId={{B7E6F3A2-4C8D-4E2B-9A47-SMORXIRP2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Layer 1 - the install password. Encryption=yes also encrypts the
; packed files with this password, so extracting Setup.exe without it fails.
Password=Inspection_Moriya@2026_ingenious#padma@8441$1564
Encryption=yes
; Install per-user in LocalAppData: no admin prompt, and the app can
; write its working folders (.Temp, Logs, .data) without permission errors.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\SmorX Inspection Report
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=SmorX_InspectionReport_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Everything produced by PyInstaller onedir build
Source: "..\backend\dist\SmorXInspectionReport\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove app working folders on uninstall (activation.dat in ProgramData stays)
Type: filesandordirs; Name: "{app}\.Temp"
Type: filesandordirs; Name: "{app}\Logs"
