# Auto Ballooning & Inspection Report Web Application

Web application for engineering drawing auto-ballooning (YOLO detection) and inspection report generation.

## Structure

- `frontend/` — Static UI (dashboard, login, admin, inspection report)
- `backend/` — FastAPI server (`serve_balloon.py`), Auto Ballooning module, auth, and assets

## Run locally

```powershell
cd backend
pip install -r requirements.txt
$env:SMORX_DISABLE_BALLOON_AUTH = "1"   # optional: skip auth in dev
python serve_balloon.py
```

Open http://127.0.0.1:9080/app

## Configuration

Copy `backend/default_config.json` from your environment template (not committed). Place `AutoBallooningModel.pt` under `backend/Resources/models/` if not already present.

## License

Proprietary — SmorX.ai
