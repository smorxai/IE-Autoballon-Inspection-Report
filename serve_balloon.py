"""
Render / root entrypoint when Start Command runs from repo root (not backend/).

Exposes `app` for: uvicorn serve_balloon:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent / "backend"
_TARGET = _BACKEND / "serve_balloon.py"
if not _TARGET.is_file():
    raise RuntimeError(f"Missing backend app: {_TARGET}")

_spec = importlib.util.spec_from_file_location("balloon_serve", _TARGET)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load {_TARGET}")

_mod = importlib.util.module_from_spec(_spec)
sys.modules["balloon_serve"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app
