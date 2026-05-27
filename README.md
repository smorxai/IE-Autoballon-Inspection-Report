# Auto Ballooning & Inspection Report Web Application

Web application for engineering drawing auto-ballooning (YOLO detection) and inspection report generation.

## Structure

- `frontend/` — Static UI (dashboard, login, admin, inspection report)
- `backend/` — FastAPI server (`serve_balloon.py`), Auto Ballooning module, auth, and assets

## Run locally

```powershell
cd backend
pip install -r requirements.txt
# Add DATABASE_URL + SUPER_ADMIN_* to backend/.env (see .env.example)
python serve_balloon.py
```

Open http://127.0.0.1:9080/login — you must log in before using `/app`.

For local dev **without** login, set `SMORX_DISABLE_BALLOON_AUTH=1` in `.env` (not recommended once PostgreSQL is configured).

## Configuration

Copy `backend/default_config.json` from your environment template (not committed). Place `AutoBallooningModel.pt` under `backend/Resources/models/` if not already present.

## License

Proprietary — SmorX.ai
