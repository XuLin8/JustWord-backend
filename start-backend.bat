@echo off
chcp 65001 >nul
title JustWord Backend

echo ============================================
echo   JustWord Backend
echo ============================================
echo.

::cd /d F:\Dev\JustWord-backend
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found!
    echo.
    echo Expected:
    echo F:\Dev\JustWord-backend\venv\Scripts\python.exe
    echo.
    pause
    exit /b 1
)

echo Starting Backend...
echo URL: http://localhost:3000
echo.

set "PYTHONIOENCODING=utf-8"

venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload --no-use-colors

pause