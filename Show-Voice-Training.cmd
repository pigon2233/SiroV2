@echo off
rem Double-click: open the SIRO voice-training progress page in a web browser
rem (it refreshes itself every 5 s). Closing the tab does not affect training.
rem Keep this file ASCII-only. Opens Chrome/Edge explicitly because .html may be
rem associated with another program.
set "DIR=%LOCALAPPDATA%\siro-voice-training"
set "PAGE=%DIR%\index.html"
if not exist "%DIR%" mkdir "%DIR%"
wsl -d Ubuntu --cd "%~dp0." -- bash -c "(setsid nohup bash scripts/tts_train/status_html_loop.sh >/dev/null 2>&1 < /dev/null &); sleep 4"
set "BROWSER="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if defined BROWSER (start "" "%BROWSER%" "%PAGE%") else (start "" "%PAGE%")
