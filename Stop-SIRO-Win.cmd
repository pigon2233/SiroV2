@echo off
rem Closes the Windows pet (only the desktop-win Electron, not other Electron apps) and stops the SIRO service in WSL.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='electron.exe'\" | Where-Object { $_.ExecutablePath -like '*desktop-win*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-stop"
pause
