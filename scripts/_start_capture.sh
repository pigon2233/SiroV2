#!/usr/bin/env bash
set -u
rm -f /tmp/siro-vrm.log /tmp/siro-start-capture.log
COMPANION_BACKEND_ONLY=1 "$HOME/.local/bin/siro-companion-vrm" > /tmp/siro-start-capture.log 2>&1 &
pid=$!
echo "pid=$pid"
for i in $(seq 1 40); do
  if curl -fs -m1 http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    echo ready_at=$i
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    echo died_at=$i
    break
  fi
  sleep 0.5
done
echo "--- capture ---"
cat /tmp/siro-start-capture.log
echo "--- vrm log ---"
cat /tmp/siro-vrm.log 2>/dev/null || true
exit 1
