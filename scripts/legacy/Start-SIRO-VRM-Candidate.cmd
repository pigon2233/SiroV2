@echo off
rem Legacy candidate entry. Use Start-SIRO-VRM-Win.cmd /candidate instead.
"%SystemRoot%\System32\wsl.exe" -d Ubuntu -- bash -lc "exec ~/.local/bin/siro-companion-vrm-candidate"
if errorlevel 1 (
  echo SIRO VRM could not start. See docs\WSL_SETUP.md for diagnostics.
  pause
)
