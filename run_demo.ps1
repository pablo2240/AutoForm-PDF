# AutoForm PDF - Demo Launcher Script
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "       Iniciando AutoForm PDF Demo (PoC)           " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Start Backend in background
Write-Host "`n[1/2] Levantando Backend FastAPI en http://localhost:8000 ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", ".\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

# 2. Start Frontend in background
Write-Host "[2/2] Levantando Frontend Vite en http://localhost:5173 ..." -ForegroundColor Yellow
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd frontend && npm run dev"

Write-Host "`n===================================================" -ForegroundColor Green
Write-Host " Demo lista! Abre en tu navegador: http://localhost:5173" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
