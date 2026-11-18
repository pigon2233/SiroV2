#!/usr/bin/env bash
# Rewrite the corpus-generation progress page every 5 s (read-only; never
# opens a window). Started by Show-Corpus-Progress.cmd; a pidfile keeps one
# copy. Exits after an hour without new generation data.
REPO=$(cd "$(dirname "$0")/../.." && pwd)
GEN=${GEN_DIR:-$HOME/tts-train/data/siro-regen}
OUT="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")/siro-corpus/progress.html"
mkdir -p "$(dirname "$OUT")"
PIDFILE=$HOME/tts-train/corpus_monitor_loop.pid
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then exit 0; fi
echo $$ > "$PIDFILE"
idle=0; last=""
while :; do
  python3 "$REPO/scripts/tts_train/corpus_monitor.py" --gen-dir "$GEN" --html "$OUT"
  cur=$(stat -c %Y "$GEN/progress.jsonl" 2>/dev/null)
  if [ "$cur" != "$last" ]; then idle=0; last=$cur; else idle=$((idle + 1)); fi
  [ "$idle" -ge 720 ] && { rm -f "$PIDFILE"; exit 0; }
  sleep 5
done
