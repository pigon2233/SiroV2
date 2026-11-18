#!/usr/bin/env bash
# Rewrite the training progress page every 5 s (read-only on training files).
# Started by Show-Voice-Training.cmd; a pidfile keeps it to one copy. Stops by
# itself once training has been finished or stopped for an hour.
OUT=${1:-$(cd "$(dirname "$0")/../.." && pwd)/.scratch/voice-training.html}
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
