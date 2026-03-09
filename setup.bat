@echo off
setlocal EnableDelayedExpansion
title Vibe-to-Print Engine — First-Time Setup

echo.
echo ============================================================
echo   Vibe-to-Print Engine — First-Time Setup
echo ============================================================
echo.

REM ── 1. Check for Python ─────────────────────────────────────
echo [1/4] Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Python not found. Installing via winget...
    winget install --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
    if %errorlevel% neq 0 (
        echo.
        echo   ERROR: winget install failed.
        echo   Please install Python 3.11+ manually from https://python.org/downloads
        echo   Make sure to tick "Add Python to PATH" during install.
        pause
        exit /b 1
    )
    echo   Python installed. Refreshing PATH...
    REM Refresh PATH so python is found in this session
    for /f "tokens=*" %%i in ('where python 2^>nul') do set PYTHON=%%i
) else (
    for /f "tokens=*" %%i in ('where python') do set PYTHON=%%i
    echo   Found Python: !PYTHON!
)

REM Verify python is callable
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   Python still not found on PATH after install.
    echo   Please restart this script OR open a NEW Command Prompt and try again.
    pause
    exit /b 1
)
python --version

REM ── 2. Create virtual environment ───────────────────────────
echo.
echo [2/4] Creating virtual environment (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo   Virtual environment created.
) else (
    echo   Virtual environment already exists, skipping.
)

REM ── 3. Install dependencies ──────────────────────────────────
echo.
echo [3/4] Installing dependencies (this may take a minute)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo   All packages installed successfully.

REM ── 4. Done ─────────────────────────────────────────────────
echo.
echo [4/4] Setup complete!
echo.
echo ============================================================
echo   To run the app, double-click  run.bat
echo   or type:  streamlit run app.py
echo ============================================================
echo.
pause
