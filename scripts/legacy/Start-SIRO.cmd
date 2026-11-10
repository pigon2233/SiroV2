@echo off
rem Legacy Live2D/GTK entry. Daily use is the repo-root Start-SIRO-VRM-Win.cmd.
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-companion"
if errorlevel 1 (
  echo SIRO could not start. See docs\WSL_SETUP.md for diagnostics.
  pause
)
