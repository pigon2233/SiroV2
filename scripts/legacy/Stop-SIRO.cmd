@echo off
rem Legacy stop. It does not close the Windows Electron pet. Use Start-SIRO-VRM-Win.cmd /stop.
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-stop"
pause
