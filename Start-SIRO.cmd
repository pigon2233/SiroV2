@echo off
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-companion"
if errorlevel 1 (
  echo SIRO could not start. See docs\WSL_SETUP.md for diagnostics.
  pause
)
