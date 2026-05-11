@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  One-time setup: creates a "Video Generator" shortcut on your Desktop
REM  that launches start.bat. Pin it to Start/Taskbar for one-click access.
REM ─────────────────────────────────────────────────────────────────────

setlocal
cd /d "%~dp0"
set "TARGET=%cd%\start.bat"
set "WORKDIR=%cd%"
set "SHORTCUT=%USERPROFILE%\Desktop\Video Generator.lnk"
set "ONEDRIVE_DESKTOP=%USERPROFILE%\OneDrive\Desktop\Video Generator.lnk"
REM Windows shell icon: shell32.dll index 137 is the video/film icon.
set "ICON=%SystemRoot%\System32\SHELL32.dll,137"

REM Use PowerShell's WScript.Shell COM to create a proper .lnk file.
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut('%SHORTCUT%');" ^
  "$lnk.TargetPath = '%TARGET%';" ^
  "$lnk.WorkingDirectory = '%WORKDIR%';" ^
  "$lnk.IconLocation = '%ICON%';" ^
  "$lnk.Description = 'Video Generator v2 — launch the local server and open in browser';" ^
  "$lnk.Save();" ^
  "if (Test-Path '%USERPROFILE%\OneDrive\Desktop') {" ^
  "  $lnk2 = $ws.CreateShortcut('%ONEDRIVE_DESKTOP%');" ^
  "  $lnk2.TargetPath = '%TARGET%';" ^
  "  $lnk2.WorkingDirectory = '%WORKDIR%';" ^
  "  $lnk2.IconLocation = '%ICON%';" ^
  "  $lnk2.Description = 'Video Generator v2';" ^
  "  $lnk2.Save();" ^
  "}"

if errorlevel 1 (
    echo.
    echo [ERROR] Could not create the shortcut.
    echo         Try right-clicking start.bat and choosing
    echo         "Send to" -^> "Desktop ^(create shortcut^)" instead.
    pause
    exit /b 1
)

echo.
echo  Shortcut created on your Desktop:
echo     %SHORTCUT%
if exist "%USERPROFILE%\OneDrive\Desktop" (
    echo     %ONEDRIVE_DESKTOP%
)
echo.
echo  To launch the app: double-click "Video Generator" on your desktop.
echo  To pin it: right-click the shortcut -^> Pin to Start  or  Pin to taskbar.
echo.
pause
