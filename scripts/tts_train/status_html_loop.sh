#!/usr/bin/env bash
# Rewrite the training progress page every 5 s (read-only on training files;
# never opens any window). Started by Show-Voice-Training.cmd; a pidfile keeps
# it to one copy. The page lives in %LOCALAPPDATA%\siro-voice-training, outside
# the repo, so editors / the Claude app do not reopen it on every rewrite.
#
# Owner request (2026-11-18): when training finishes (train_siro.sh logs
# "=== exit 0"), delete the page folder and Show-Voice-Training.cmd, then exit.
# If training is merely paused (STOP file) for an hour, just exit.
REPO=$(cd "$(dirname "$0")/../.." && pwd)
RUN=$HOME/tts-train/runs/${RUN_NAME:-siro-sweet-b-v1}
if [ -n "${1:-}" ]; then
  OUT=$1
else
  OUT="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")/siro-voice-training/index.html"
fi
mkdir -p "$(dirname "$OUT")"
PIDFILE=$HOME/tts-train/status_html_loop.pid
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then exit 0; fi
echo $$ > "$PIDFILE"
idle=0
while :; do
  python3 "$REPO/scripts/tts_train/training_status.py" --run "$RUN" --html "$OUT"
  if pgrep -f "[t]rain.py --c" >/dev/null; then
    idle=0
  else
    if tail -n 1 "$RUN/console.log" 2>/dev/null | grep -q '^=== exit 0 '; then
      rm -rf "$(dirname "$OUT")" "$REPO/Show-Voice-Training.cmd"
      echo "$(date -Is) training finished; removed progress page and Show-Voice-Training.cmd" >> "$RUN/console.log"
      rm -f "$PIDFILE"; exit 0
    fi
    idle=$((idle + 1))
  fi
  [ "$idle" -ge 720 ] && { rm -f "$PIDFILE"; exit 0; }
  sleep 5
done
