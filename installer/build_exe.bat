@echo off
REM ============================================================
REM  SmorX Inspection Report - build the Windows exe (Layer 4)
REM  Run from anywhere:  installer\build_exe.bat
REM  Output:  backend\dist\SmorXInspectionReport\SmorXInspectionReport.exe
REM ============================================================
setlocal
cd /d "%~dp0\..\backend"

echo [1/3] Installing PyInstaller (if missing)...
pip show pyinstaller >nul 2>&1 || pip install pyinstaller

echo [2/3] Building exe (PyInstaller onedir - recommended for torch/ultralytics)...
pyinstaller --noconfirm --clean ^
  --name SmorXInspectionReport ^
  --paths . ^
  --paths Modules ^
  --paths Dependencies ^
  --add-data "Resources;Resources" ^
  --add-data "default_config.json;." ^
  --hidden-import AutoBallooning.tasks ^
  --hidden-import drawing_regions ^
  --hidden-import dim_line_detect ^
  --hidden-import config ^
  --hidden-import mongodb ^
  --hidden-import pdf_vector_text ^
  --hidden-import licensing.prompt ^
  --collect-data ultralytics ^
  run_app.py

if errorlevel 1 (
  echo BUILD FAILED.
  exit /b 1
)

echo [3/3] Copying runtime config (.env) next to the exe (optional)...
if exist ".env" copy /y ".env" "dist\SmorXInspectionReport\.env" >nul

echo.
echo Done. Test it:   backend\dist\SmorXInspectionReport\SmorXInspectionReport.exe
echo Then build the installer with Inno Setup:  installer\setup.iss
echo.
REM ------------------------------------------------------------
REM  OPTIONAL Nuitka alternative (much longer build, stronger
REM  obfuscation of YOUR code; heavy deps stay as libraries):
REM
REM    pip install nuitka
REM    python -m nuitka --standalone --output-dir=dist-nuitka ^
REM      --include-data-dir=Resources=Resources ^
REM      --include-data-files=default_config.json=default_config.json ^
REM      --include-package=licensing --include-package=auth ^
REM      --include-module=config --include-module=mongodb ^
REM      run_app.py
REM ------------------------------------------------------------
endlocal
