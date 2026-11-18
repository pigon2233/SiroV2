#!/usr/bin/env bash
# Rewrite the training progress page every 5 s (read-only on training files;
# never opens any window). Started by Show-Voice-Training.cmd; a pidfile keeps
# it to one copy. Stops by itself once training has been stopped for an hour.
# The page lives in %LOCALAPPDATA%\siro-voice-training, outside the repo, so
# editors / the Claude app do not reopen it on every rewrite.
if [ -n "${1:-}" ]; then
  OUT=$1
else
  OUT="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")/siro-voice-training/index.html"
fi
mkdir -p "$(dirname "$OUT")"
PIDFILE=$HOME/tts-train/status_html_loop.pid
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then exit 0; fi
echo $$ > "$PIDFILE"
HERE=$(dirname "$0")
idle=0
while :; do
  python3 "$HERE/training_status.py" --html "$OUT"
  if pgrep -f "[t]rain.py --c" >/dev/null; then idle=0; else idle=$((idle + 1)); fi
  [ "$idle" -ge 720 ] && { rm -f "$PIDFILE"; exit 0; }
  sleep 5
done
