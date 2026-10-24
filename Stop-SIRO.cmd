@echo off
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-stop"
pause
