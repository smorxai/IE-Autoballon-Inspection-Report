"""
SmorX Inspection Report — packaged-app launcher (PyInstaller / Nuitka entry).

Flow:
  1. Check machine-bound activation (activation.dat).
  2. First launch → license key dialog → create encrypted activation.
  3. Start the FastAPI server and open the browser at /login.
"""
from __future__ import annotations

import os
import sys
import threading
import webbrowser
from pathlib import Path


def _app_dir() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller onedir/onefile
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> int:
    app_dir = _app_dir()
    os.chdir(app_dir)
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    # Layers 2/3/5: license key + machine binding + encrypted activation file.
    from licensing.prompt import ensure_activated

    if not ensure_activated():
        print("Activation required. Exiting.")
        return 1

    host = os.environ.get("BALLOON_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("BALLOON_UI_PORT", "9090"))

    url = f"http://{host}:{port}/login"
    threading.Timer(3.0, lambda: webbrowser.open(url)).start()
    print(f"SmorX Inspection Report  ->  {url}")

    import uvicorn

    from serve_balloon import app  # heavy import — after activation check

    uvicorn.run(app, host=host, port=port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
