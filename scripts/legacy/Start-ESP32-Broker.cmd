@echo off
rem Legacy entry. Daily use is Start-SIRO-VRM-Win.cmd, which starts this broker only when configured.
rem Authenticated LAN MQTT broker for the ESP32 node. Credentials come from the git-ignored secrets.h.
set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set VENV=%LOCALAPPDATA%\siro\broker-venv
if not exist "%VENV%\Scripts\python.exe" (
  python -m venv "%VENV%" || exit /b 1
  "%VENV%\Scripts\python.exe" -m pip install -q amqtt==0.12.1 argon2-cffi==25.1.0 || exit /b 1
)
"%VENV%\Scripts\python.exe" "%ROOT%\scripts\esp32_mqtt_broker.py"
