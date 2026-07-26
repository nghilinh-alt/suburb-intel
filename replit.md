# Suburb Intel

Australia's government-data-driven property investment decision engine. FastAPI backend + React/Vite frontend.

## Architecture

- **Backend**: FastAPI (Python 3.12) served by Uvicorn on port 8000
- **Frontend**: React 19 + Vite dev server on port 5000 (proxies `/api/*` → backend)
- **Database**: SQLite (dev) via `backend/suburb_intel_dev.db`; PostgreSQL available via env override

## Running locally on Replit

Two workflows are configured:

| Workflow | Command | Port |
|---|---|---|
| `Backend API` | `cd backend && python run_dev.py && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | 8000 (console) |
| `Start application` | `cd frontend && npm run dev` | 5000 (webview) |

Start the **Backend API** workflow first, then **Start application**. The preview pane shows the frontend.

## API proxy

`vite.config.ts` proxies all `/api/*` requests to `http://localhost:8000`, stripping the `/api` prefix. So frontend code calls `/api/suburb/123` which hits `GET /suburb/123` on the backend.

## Environment

- `backend/.env` — local env vars (DATABASE_URL, PROPRADAR_API_KEY)
- Default: `DATABASE_URL=sqlite+aiosqlite:///./suburb_intel_dev.db`

## User preferences

- Keep existing project structure intact
