@echo off
rem Double-click: open the SIRO corpus-generation progress page in a web browser
rem (refreshes itself every 5 s). Closing the tab does not affect generation.
rem Keep this file ASCII-only (cmd reads it in the ANSI code page).
set "DIR=%LOCALAPPDATA%\siro-corpus"
set "PAGE=%DIR%\progress.html"
if not exist "%DIR%" mkdir "%DIR%"
wsl -d Ubuntu --cd "%~dp0." -- bash -c "(setsid nohup bash scripts/tts_train/corpus_monitor_loop.sh >/dev/null 2>&1 < /dev/null &); sleep 4"
set "BROWSER="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined BROWSER if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if defined BROWSER (start "" "%BROWSER%" "%PAGE%") else (start "" "%PAGE%")
