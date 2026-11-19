@echo off
rem Double-click: open the SIRO voice monitor (Rust/egui window, read-only).
rem Build first if needed: cd tools\siro-monitor && cargo build --release
rem Keep this file ASCII-only.
cd /d "%~dp0tools\siro-monitor"
start "" "target\release\siro-monitor.exe"
