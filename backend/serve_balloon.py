"""
Standalone YOLO detection API + static UI (does NOT use main.py).

Use this when another process on :9000 causes 404s or wrong `main` imports.

  cd AI_Engine
  python backend/serve_balloon.py

Repo layout: frontend/ (static UI) and backend/ (API + pipeline).

Then open the URL printed (default http://127.0.0.1:9080).

Returns JSON your frontend / .NET / Java can use to draw balloon circles:
  - detections[].bbox, class_name, confidence
  - drawing_annotations[] with id, BBox, TextPos (center), AnnotationType

Env:
  BALLOON_UI_PORT=9080   (optional)
  BALLOON_UI_HOST=127.0.0.1
"""
from __future__ import annotations

import os
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import cv2
from pydantic import BaseModel, Field

_BACKEND_DIR = Path(__file__).resolve().parent
_APP_ROOT = _BACKEND_DIR.parent
os.chdir(_BACKEND_DIR)
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
for _p in ("Modules", "Dependencies", "Resources", ".Temp"):
    _d = str(_BACKEND_DIR / _p)
    if _d not in sys.path:
        sys.path.append(_d)

import config
import mongodb as db
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from openpyxl import Workbook
from starlette.middleware.sessions import SessionMiddleware

from Security.balloon_auth import (
    hash_password as pw_hash,
    is_admin_email,
    is_gmail,
    trial_expired,
    trial_remaining_sec,
    verify_password,
)
from Security.balloon_auth_store import (
    create_user,
    get_user,
    init_db,
    list_users,
    set_paid,
    update_trial_start,
)
from Security.trial_auth import (
    check_login_rate_limit,
    clear_login_attempts,
    record_login_failure,
    session_secret,
)

config.InitConfiguration()
_Db = config.GetConfiguration("DATABASE")
if _Db:
    if _Db.get("URI"):
        db.Connect(uri=_Db["URI"])
    else:
        db.Connect(_Db.get("ADDRESS", "localhost"), _Db.get("PORT", 27017))

from AutoBallooning.tasks import (  # noqa: E402
    _vision_llm_message,
    get_yolo_weights_path_loaded,
    run_drawing_yolo_detection,
)

_UPLOAD_ROOT = _BACKEND_DIR / ".Temp" / "balloon_ui_uploads"
_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

init_db()

app = FastAPI(
    title="Auto Ballooning & inspection report Software System",
    version="1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    max_age=3600 * 24 * 14,
    same_site="lax",
    https_only=False,
)

# In-repo: ../frontend. Standalone GitHub export: UI under Resources/balloon_ui (see export script).
if (_BACKEND_DIR / "Resources" / "balloon_ui" / "index.html").is_file():
    _UI_DIR = _BACKEND_DIR / "Resources" / "balloon_ui"
else:
    _UI_DIR = _APP_ROOT / "frontend"
_STATIC_DIR = _UI_DIR / "static"
if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR)), name="balloon_assets")


def auth_disabled() -> bool:
    return os.environ.get("SMORX_DISABLE_BALLOON_AUTH", "").strip().lower() in ("1", "true", "yes")


def session_user(request: Request) -> Optional[dict[str, Any]]:
    if auth_disabled():
        return {"email": "dev@local", "role": "admin", "paid": True, "trial_started_at": None}
    email = request.session.get("balloon_email")
    if not email:
        return None
    return get_user(str(email))


async def require_user(request: Request) -> dict[str, Any]:
    u = session_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Login required")
    if u.get("role") != "admin" and not u.get("paid") and trial_expired(u):
        raise HTTPException(status_code=402, detail="Payment required")
    return u


async def require_admin(request: Request) -> dict[str, Any]:
    u = await require_user(request)
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return u


class AuthBody(BaseModel):
    email: str
    password: str = ""


class SetPaidBody(BaseModel):
    email: str
    paid: bool = True


def _html_no_cache(path: Path) -> FileResponse:
    resp = FileResponse(str(path), media_type="text/html; charset=utf-8")
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _drawing_annotations_from_detections(detections: list) -> list:
    out = []
    for i, d in enumerate(detections or [], start=1):
        bb = d.get("bbox")
        if not bb or len(bb) < 4:
            continue
        x1, y1, x2, y2 = bb[0], bb[1], bb[2], bb[3]
        out.append(
            {
                "id": i,
                "AnnotationType": d.get("class_name") or "Dimensions",
                "BBox": [int(x1), int(y1), int(x2), int(y2)],
                "TextPos": [int((x1 + x2) / 2), int((y1 + y2) / 2)],
            }
        )
    return out


def _extract_detection_text_llm(image_path: str, detections: list) -> list:
    img = cv2.imread(image_path)
    if img is None:
        return []
    h, w = img.shape[:2]
    prompt = (
        "Read the engineering annotation text in this crop. "
        "Return only exact value/characters. "
        "If unreadable, return empty."
    )
    items = []
    for i, d in enumerate(detections or [], start=1):
        bb = d.get("bbox") or []
        if len(bb) < 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in bb[:4]]
        pad = 6
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)
        if x2 <= x1 or y2 <= y1:
            continue
        crop = img[y1:y2, x1:x2]
        ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        detected_text = ""
        if ok:
            try:
                val = _vision_llm_message(buf.tobytes(), prompt, max_tokens=80, temperature=0.0, top_p=1.0)
                detected_text = (val or "").replace("\r", " ").replace("\n", " ").strip()
            except Exception:
                detected_text = ""
        items.append(
            {
                "balloon_number": i,
                "class_name": d.get("class_name", ""),
                "confidence": d.get("confidence", ""),
                "detected_text": detected_text,
            }
        )
    return items


@app.get("/health")
async def health():
    return {"ok": True, "service": "serve_balloon", "port_hint": "default 9080"}


@app.get("/")
async def root_redirect(request: Request):
    if auth_disabled():
        return RedirectResponse("/app")
    u = session_user(request)
    if not u:
        return RedirectResponse("/login")
    if u.get("role") != "admin" and not u.get("paid") and trial_expired(u):
        return RedirectResponse("/payment")
    return RedirectResponse("/app")


@app.get("/login")
async def login_page():
    p = _UI_DIR / "login.html"
    if not p.is_file():
        raise HTTPException(500, "Missing login.html")
    return _html_no_cache(p)


@app.get("/payment")
async def payment_page():
    p = _UI_DIR / "payment.html"
    if not p.is_file():
        raise HTTPException(500, "Missing payment.html")
    return _html_no_cache(p)


@app.get("/inspection-report")
async def inspection_report_page(request: Request):
    p = _UI_DIR / "inspection_report.html"
    if not p.is_file():
        raise HTTPException(500, "Missing inspection_report.html")
    if auth_disabled():
        return _html_no_cache(p)
    u = session_user(request)
    if not u:
        return RedirectResponse("/login")
    if u.get("role") != "admin" and not u.get("paid") and trial_expired(u):
        return RedirectResponse("/payment")
    return _html_no_cache(p)


@app.get("/app")
async def app_page(request: Request):
    index = _UI_DIR / "index.html"
    if not index.is_file():
        return JSONResponse(status_code=500, content={"ok": False, "error": "Missing index.html"})
    if auth_disabled():
        return _html_no_cache(index)
    u = session_user(request)
    if not u:
        return RedirectResponse("/login")
    if u.get("role") != "admin" and not u.get("paid") and trial_expired(u):
        return RedirectResponse("/payment")
    return _html_no_cache(index)


@app.get("/admin")
async def admin_page(request: Request):
    p = _UI_DIR / "admin.html"
    if not p.is_file():
        raise HTTPException(500, "Missing admin.html")
    u = session_user(request)
    if not u:
        return RedirectResponse("/login")
    if u.get("role") != "admin":
        raise HTTPException(403, detail="Admin only")
    return _html_no_cache(p)


@app.post("/api/auth/register")
async def api_register(body: AuthBody):
    if auth_disabled():
        return {"ok": True, "message": "Registration skipped (auth disabled)"}
    if not is_gmail(body.email):
        raise HTTPException(400, detail="Only @gmail.com addresses are allowed")
    pwd = (body.password or "").strip()
    if not pwd:
        raise HTTPException(400, detail="Password is required")
    if len(pwd) < 8:
        raise HTTPException(400, detail="Password must be at least 8 characters")
    if get_user(body.email):
        raise HTTPException(400, detail="Account already exists")
    role = "admin" if is_admin_email(body.email) else "user"
    create_user(body.email, pw_hash(pwd), role=role)
    return {"ok": True}


@app.post("/api/auth/login")
async def api_login(request: Request, body: AuthBody):
    if auth_disabled():
        request.session["balloon_email"] = "dev@local"
        return {"ok": True, "dev": True}
    if not is_gmail(body.email):
        raise HTTPException(400, detail="Only @gmail.com addresses are allowed")
    pwd = (body.password or "").strip()
    if not pwd:
        raise HTTPException(400, detail="Password is required")
    check_login_rate_limit(request)
    u = get_user(body.email)
    if not u:
        raise HTTPException(404, detail="Account not found. Create account first.")
    if not verify_password(pwd, u.get("password_hash", "")):
        record_login_failure(request)
        raise HTTPException(401, detail="Invalid email or password")
    clear_login_attempts(request)
    email = body.email.strip().lower()
    if u.get("role") != "admin" and not u.get("paid") and u.get("trial_started_at") is None:
        update_trial_start(email, time.time())
    request.session["balloon_email"] = email
    return {"ok": True}


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
async def api_me(request: Request):
    u = session_user(request)
    if not u:
        return {"ok": False, "logged_in": False}
    rem = trial_remaining_sec(u)
    return {
        "ok": True,
        "logged_in": True,
        "email": u["email"],
        "role": u.get("role"),
        "paid": u.get("paid"),
        "trial_expired": trial_expired(u) if u.get("role") != "admin" else False,
        "trial_remaining_sec": rem,
    }


@app.get("/api/admin/users")
async def api_admin_users(_request: Request, _u: dict = Depends(require_admin)):
    rows = []
    for r in list_users():
        ts = r.get("trial_started_at")
        ts_s = ""
        if ts is not None:
            ts_s = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
        rows.append(
            {
                "email": r["email"],
                "role": r["role"],
                "paid": bool(r["paid"]),
                "trial_started_at": ts_s,
            }
        )
    return {"ok": True, "users": rows}


@app.post("/api/admin/set-paid")
async def api_admin_set_paid(_request: Request, body: SetPaidBody, _u: dict = Depends(require_admin)):
    n = set_paid(body.email, body.paid)
    if not n:
        raise HTTPException(404, detail="User not found")
    return {"ok": True}


@app.post("/api/v1/detect")
async def api_detect(
    file: UploadFile = File(...),
    _user: dict = Depends(require_user),
):
    if not file.filename:
        raise HTTPException(422, "No filename")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    if suffix not in allowed:
        raise HTTPException(400, f"Unsupported type {suffix}. Use PDF or image.")

    job = uuid.uuid4().hex
    work = _UPLOAD_ROOT / job
    work.mkdir(parents=True, exist_ok=True)
    dest = work / f"input{suffix}"

    try:
        with dest.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)

        payload, err = run_drawing_yolo_detection(str(dest), str(work), file.filename)
        if err:
            return JSONResponse(status_code=400, content={"ok": False, "error": err})

        dets = payload.get("detections") or []
        payload["drawing_annotations"] = _drawing_annotations_from_detections(dets)
        # Use saved input path for optional text extraction; failures return [].
        payload["balloon_items"] = _extract_detection_text_llm(str(dest), dets)
        payload["weights_path"] = get_yolo_weights_path_loaded()

        return JSONResponse(
            content={
                "ok": True,
                "version": 1,
                "filename": file.filename,
                "detection": payload,
            }
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.post("/api/v1/export-excel")
async def api_export_excel(
    request: Request,
    _user: dict = Depends(require_user),
):
    payload = await request.json()
    detection = payload.get("detection") or {}
    filename = payload.get("filename") or "drawing"

    wb = Workbook()
    ws_meta = wb.active
    ws_meta.title = "summary"
    ws_meta.append(["filename", filename])
    ws_meta.append(["count", detection.get("count", 0)])
    ws_meta.append(["width", detection.get("width", "")])
    ws_meta.append(["height", detection.get("height", "")])
    ws_meta.append(["input_kind", detection.get("input_kind", "")])
    ws_meta.append(["weights_path", detection.get("weights_path", "")])

    ws_det = wb.create_sheet("detections")
    ws_det.append(["id", "class_name", "confidence", "x1", "y1", "x2", "y2"])
    for idx, d in enumerate(detection.get("detections") or [], start=1):
        bb = d.get("bbox") or [None, None, None, None]
        ws_det.append(
            [
                idx,
                d.get("class_name", ""),
                d.get("confidence", ""),
                bb[0] if len(bb) > 0 else "",
                bb[1] if len(bb) > 1 else "",
                bb[2] if len(bb) > 2 else "",
                bb[3] if len(bb) > 3 else "",
            ]
        )

    ws_ann = wb.create_sheet("balloons")
    ws_ann.append(["id", "AnnotationType", "bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2", "text_x", "text_y"])
    for a in detection.get("drawing_annotations") or []:
        bb = a.get("BBox") or [None, None, None, None]
        tp = a.get("TextPos") or [None, None]
        ws_ann.append(
            [
                a.get("id", ""),
                a.get("AnnotationType", ""),
                bb[0] if len(bb) > 0 else "",
                bb[1] if len(bb) > 1 else "",
                bb[2] if len(bb) > 2 else "",
                bb[3] if len(bb) > 3 else "",
                tp[0] if len(tp) > 0 else "",
                tp[1] if len(tp) > 1 else "",
            ]
        )

    ws_items = wb.create_sheet("balloon_items")
    ws_items.append(["balloon_number", "class_name", "confidence", "detected_text"])
    for it in detection.get("balloon_items") or []:
        ws_items.append(
            [
                it.get("balloon_number", ""),
                it.get("class_name", ""),
                it.get("confidence", ""),
                it.get("detected_text", ""),
            ]
        )

    buff = BytesIO()
    wb.save(buff)
    xlsx_name = f"AutoBallooning_{Path(filename).stem}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{xlsx_name}"'}
    return Response(
        content=buff.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("BALLOON_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("BALLOON_UI_PORT", "9080"))
    print(f"Auto Ballooning & inspection report Software System  →  http://{host}:{port}/")
    print(f"Login page              →  http://{host}:{port}/login")
    print(f"App (after login)       →  http://{host}:{port}/app")
    print(f"POST detection JSON     →  http://{host}:{port}/api/v1/detect")
    print("Set BALLOON_ADMIN_EMAILS=admin@gmail.com for admin. SMORX_DISABLE_BALLOON_AUTH=1 skips login (dev).")
    uvicorn.run(app, host=host, port=port, reload=False)
