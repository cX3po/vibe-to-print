@echo off
title Vibe-to-Print Engine
cd /d "%~dp0"

REM ── Activate virtual environment ────────────────────────────
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM ── Launch Streamlit ────────────────────────────────────────
echo.
echo Starting Vibe-to-Print Engine...
echo The app will open in your browser automatically.
echo Press Ctrl+C in this window to stop the server.
echo.

streamlit run app.py --server.headless false --browser.gatherUsageStats false
pause
