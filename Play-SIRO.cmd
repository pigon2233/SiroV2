@echo off
chcp 65001 >nul
rem Ask SIRO to play/operate a program. Usage: Play-SIRO.cmd "goal" [seconds_before_start]
rem Switch control on from the tray first; click the game window to the front during the delay.
"%SystemRoot%\System32\wsl.exe" -d Ubuntu --cd "%~dp0." -- bash scripts/computer-play.sh "%~1" "%~2"
pause
