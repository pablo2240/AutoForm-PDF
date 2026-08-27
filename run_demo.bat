@echo off
echo ===================================================
echo        Iniciando AutoForm PDF Demo (PoC)
echo ===================================================
echo.

REM 1. Iniciar Backend FastAPI
echo [1/2] Levantando Backend FastAPI en http://localhost:8000 ...
start "AutoForm PDF - Backend API" cmd /k ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

REM 2. Iniciar Frontend Vite
echo [2/2] Levantando Frontend en http://localhost:5173 ...
cd frontend
start "AutoForm PDF - Frontend" cmd /k "npm run dev"

echo.
echo ===================================================
echo  Demo ejecutandose. Abre http://localhost:5173
echo ===================================================
pause
