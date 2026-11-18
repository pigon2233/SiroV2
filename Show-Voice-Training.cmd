@echo off
rem Double-click: open the SIRO voice-training progress page (refreshes every 5 s).
rem Closing the page does not affect training. Keep this file ASCII-only.
set "PAGE=%~dp0.scratch\voice-training.html"
if not exist "%~dp0.scratch" mkdir "%~dp0.scratch"
wsl -d Ubuntu --cd "%~dp0." -- bash -c "(setsid nohup bash scripts/tts_train/status_html_loop.sh >/dev/null 2>&1 < /dev/null &); sleep 3"
start "" "%PAGE%"
