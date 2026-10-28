@echo off
chcp 65001 >nul
rem Backend in WSL, pet as a native Windows window that stays on top (desktop-win).
rem setsid keeps the backend alive after this wsl.exe call returns; then wait until it answers.
rem ESP32 MQTT broker: started hidden only if 1883 is free and secrets.h exists (never blocks SIRO).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-esp32-broker.ps1" >nul 2>&1
"%SystemRoot%\System32\wsl.exe" -d Ubuntu --cd "%~dp0." -- bash scripts/start-win-backend
if errorlevel 1 (
  echo SIRO backend could not start. See docs\WSL_SETUP.md for diagnostics.
  pause
  exit /b 1
)
if not exist "%~dp0desktop-win\node_modules\electron\dist\electron.exe" (
  echo Run "npm install" in desktop-win first.
  pause
  exit /b 1
)
start "" /d "%~dp0desktop-win" "%~dp0desktop-win\node_modules\electron\dist\electron.exe" .
