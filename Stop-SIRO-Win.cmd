@echo off
rem Closes the Windows pet (only the desktop-win Electron, not other Electron apps) and stops the SIRO service in WSL.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | Where-Object { $_.ExecutablePath -like '*desktop-win*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
rem Also stop the ESP32 MQTT broker started by Start-SIRO-VRM-Win.cmd.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*esp32_mqtt_broker*' -or $_.CommandLine -like '*Start-ESP32-Broker*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-stop"
pause
