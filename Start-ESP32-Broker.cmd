@echo off
rem Authenticated LAN MQTT broker for the ESP32 node. Credentials come from the git-ignored secrets.h.
set VENV=%LOCALAPPDATA%\siro\broker-venv
if not exist "%VENV%\Scripts\python.exe" (
  python -m venv "%VENV%" || exit /b 1
  "%VENV%\Scripts\python.exe" -m pip install -q amqtt==0.12.1 argon2-cffi==25.1.0 || exit /b 1
)
"%VENV%\Scripts\python.exe" "%~dp0scripts\esp32_mqtt_broker.py"
