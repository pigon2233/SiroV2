#!/usr/bin/env bash
set -u
# Clear stale log so we can see a fresh start.
: > /tmp/siro-vrm.log
COMPANION_BACKEND_ONLY=1 setsid -f "$HOME/.local/bin/siro-companion-vrm" >/tmp/siro-vrm.log 2>&1 </dev/null
echo "launched"
for i in $(seq 120); do
  if curl -fs -m1 http://127.0.0.1:8000/health/ready >/dev/null; then
    echo "READY after ${i}"
    exit 0
  fi
  # If the launcher died early, dump the log.
  if ! pgrep -f 'siro-companion-vrm|start-companion|uvicorn|siro-runtime' >/dev/null 2>&1; then
    if [ "$i" -gt 4 ]; then
      echo "PROCESS_GONE after ${i}"
      tail -n 120 /tmp/siro-vrm.log || true
      exit 1
    fi
  fi
  sleep .5
done
echo "TIMEOUT"
tail -n 120 /tmp/siro-vrm.log || true
exit 1
