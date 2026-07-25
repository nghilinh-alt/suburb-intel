@echo off
REM Starts the Suburb Intel backend and frontend dev servers, each in its
REM own window so you can see logs and stop them independently (Ctrl+C).
REM Run this file from anywhere - it locates backend/ and frontend/
REM relative to its own location.

setlocal
set ROOT=%~dp0

echo Starting backend (http://localhost:8000) ...
start "Suburb Intel - Backend" cmd /k "cd /d "%ROOT%backend" && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM Give the backend a few seconds to finish booting before the frontend
REM starts making requests to it - otherwise the first few API calls
REM through Vite's proxy fail with 500s while uvicorn is still starting up.
echo Waiting for backend to finish starting...
timeout /t 5 /nobreak >nul

echo Starting frontend (http://localhost:3000) ...
start "Suburb Intel - Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"

timeout /t 3 /nobreak >nul

echo Opening the app in your browser...
start http://localhost:3000

echo.
echo Both servers are running in their own windows.
echo Close those windows (or press Ctrl+C in each) to stop them.
endlocal
