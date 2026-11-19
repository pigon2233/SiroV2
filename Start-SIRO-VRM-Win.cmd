@echo off
setlocal EnableExtensions
chcp 65001 >nul
rem Single Windows entry for SIRO.
rem   Start-SIRO-VRM-Win.cmd                         backend + Electron pet
rem   Start-SIRO-VRM-Win.cmd /backend                backend only
rem   Start-SIRO-VRM-Win.cmd /candidate              candidate VRM + pet
rem   Start-SIRO-VRM-Win.cmd /backend /candidate     candidate backend only
rem   Start-SIRO-VRM-Win.cmd /stop                   stop pet, broker, and WSL service
rem Nothing besides the pet is shown on success. ESP32 broker/OTA stay silent
rem and start only when that machine is already configured.

set "SIRO_DIR=%~dp0"
set "MODE=pet"
set "VARIANT="
set "STOP="
set "INTERNAL="
:parse
if "%~1"=="" goto parsed
if /I "%~1"=="/internal" set "INTERNAL=1" & shift & goto parse
if /I "%~1"=="/stop" set "STOP=1" & shift & goto parse
if /I "%~1"=="/backend" set "MODE=backend" & shift & goto parse
if /I "%~1"=="/candidate" set "VARIANT=candidate" & shift & goto parse
echo Unknown argument: %~1
echo Usage: Start-SIRO-VRM-Win.cmd [/backend] [/candidate] [/stop]
exit /b 2
:parsed
if defined STOP if /I not "%MODE%"=="pet" (
  echo /stop cannot be combined with other modes.
  exit /b 2
)
if defined STOP if defined VARIANT (
  echo /stop cannot be combined with other modes.
  exit /b 2
)
if defined STOP goto stop

set "SIRO_SELF=%~f0"
set "SIRO_RELAUNCH_ARGS=/internal"
if /I "%MODE%"=="backend" set "SIRO_RELAUNCH_ARGS=/internal /backend"
if defined VARIANT set "SIRO_RELAUNCH_ARGS=%SIRO_RELAUNCH_ARGS% /candidate"
if defined INTERNAL goto work
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\relaunch-win-hidden.ps1"
if not errorlevel 1 exit /b 0

:work
rem ESP32 MQTT broker and OTA relay: hidden, and only when that machine is configured.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\start-esp32-broker.ps1" >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\start-esp32-ota-relay.ps1" >nul 2>&1
set "LAUNCH_LOG=%TEMP%\siro-win-launch.txt"
if defined VARIANT (
  "%SystemRoot%\System32\wsl.exe" -d Ubuntu --cd "%SIRO_DIR%." -- bash scripts/start-win-backend candidate > "%LAUNCH_LOG%" 2>&1
) else (
  "%SystemRoot%\System32\wsl.exe" -d Ubuntu --cd "%SIRO_DIR%." -- bash scripts/start-win-backend > "%LAUNCH_LOG%" 2>&1
)
if errorlevel 1 goto failed
if /I "%MODE%"=="backend" exit /b 0
if not exist "%SIRO_DIR%desktop-win\node_modules\electron\dist\electron.exe" goto missing_electron
rem Choose the GPU before electron.exe starts. The default is the integrated adapter.
powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\set-pet-gpu-preference.ps1" -ExePath "%SIRO_DIR%desktop-win\node_modules\electron\dist\electron.exe"
start "" /d "%SIRO_DIR%desktop-win" "%SIRO_DIR%desktop-win\node_modules\electron\dist\electron.exe" .
exit /b 0

:missing_electron
powershell -NoProfile -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\show-win-notice.ps1" -Kind electron
exit /b 1

:failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%SIRO_DIR%scripts\show-win-notice.ps1" -Path "%LAUNCH_LOG%" -Kind backend
exit /b 1

:stop
rem Close only the desktop-win Electron pet, not other Electron apps, then the broker and WSL service.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | Where-Object { $_.ExecutablePath -like '*desktop-win*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*esp32_mqtt_broker*' -or $_.CommandLine -like '*Start-ESP32-Broker*' -or $_.CommandLine -like '*esp32_http_receiver*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
"%SystemRoot%\System32\wsl.exe" -d Ubuntu --cd "%SIRO_DIR%." -- bash scripts/stop-win-backend
pause
exit /b 0
