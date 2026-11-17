@echo off
REM Abre o backend (FastAPI) e o frontend (React) em janelas separadas.
cd /d %~dp0..
start "AgroSentinela - API" cmd /k "cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"
start "AgroSentinela - Frontend" cmd /k "cd frontend && npm run dev"
timeout /t 5 >nul
start http://localhost:5173
