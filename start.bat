@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  Video Generator v2 — Windows launcher
REM
REM  Double-click this file to:
REM    1. Create / activate the Python virtualenv (.venv)
REM    2. Install Python dependencies if missing
REM    3. Install HyperFrames (npm) if missing
REM    4. Open http://localhost:8765 in the browser
REM    5. Start uvicorn in the foreground (logs visible, Ctrl+C to stop)
REM ─────────────────────────────────────────────────────────────────────

setlocal enableextensions enabledelayedexpansion
title Video Generator v2
cd /d "%~dp0"

REM --- Python check -------------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python is not installed or not on PATH.
    echo         Install from https://www.python.org/downloads/windows/
    echo         During install: tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

REM --- Node / npm check ---------------------------------------------------
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Node.js / npm is not installed or not on PATH.
    echo         Install from https://nodejs.org/  (LTS or newer^).
    echo.
    pause
    exit /b 1
)

REM --- ffmpeg check -------------------------------------------------------
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARN] ffmpeg is not on PATH. Install via:
    echo        winget install Gyan.FFmpeg
    echo        Then restart this script.
    echo.
    pause
    exit /b 1
)

REM --- venv ---------------------------------------------------------------
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM --- Python deps --------------------------------------------------------
REM Only install when requirements.txt has changed (track via .install-marker).
set "REQS_HASH_FILE=.venv\.requirements-hash"
set "CURRENT_HASH="
for /f "delims=" %%H in ('certutil -hashfile requirements.txt SHA1 ^| findstr /v ":" ^| findstr /v "CertUtil"') do (
    if not defined CURRENT_HASH set "CURRENT_HASH=%%H"
)
set "PREVIOUS_HASH="
if exist "%REQS_HASH_FILE%" set /p PREVIOUS_HASH=<"%REQS_HASH_FILE%"
if not "%CURRENT_HASH%"=="%PREVIOUS_HASH%" (
    echo Installing / updating Python dependencies...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] pip install failed.
        pause
        exit /b 1
    )
    echo %CURRENT_HASH%>"%REQS_HASH_FILE%"
)

REM --- HyperFrames global install ----------------------------------------
where hyperframes >nul 2>&1
if errorlevel 1 (
    echo Installing HyperFrames globally via npm ^(one-time^)...
    call npm install -g hyperframes
    if errorlevel 1 (
        echo [ERROR] npm install -g hyperframes failed.
        echo         Try running this script as Administrator,
        echo         or change npm prefix to a user-writable folder.
        pause
        exit /b 1
    )
)

REM --- Banner + browser launch -------------------------------------------
echo.
echo ============================================================
echo   Video Generator v2 - http://localhost:8765
echo ============================================================
echo   Logs appear below. Press Ctrl+C to stop the server.
echo ============================================================
echo.

REM Open browser 3 seconds after uvicorn starts. The "start" command
REM returns immediately so it doesn't block the foreground server.
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8765"

REM --- Run uvicorn in the foreground ------------------------------------
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level info

REM If uvicorn dies (Ctrl+C or error), drop back here so the window stays
REM open and the user can read any final messages.
echo.
echo Server stopped.
pause
