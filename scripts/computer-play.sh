#!/usr/bin/env bash
# Ask SIRO to play/operate a program on this PC. Usage (WSL):
#   bash scripts/computer-play.sh "goal in your own words" [seconds_before_start=20]
# You get the delay to click the game window to the front (talking to SIRO takes the focus away).
# She only acts while the foreground program is on the allowed list in siro-computer/computer.env,
# and control must be switched on from the tray. Emergency stop: Ctrl+Alt+Shift+Esc.
set -euo pipefail
goal="${1:-}"
delay="${2:-20}"
if [ -z "$goal" ]; then
  echo '用法: computer-play.sh "要她做的事" [開始前等待秒數]' >&2
  exit 2
fi
win_home="$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')")"
env_file="$win_home/siro-computer/computer.env"
[ -f "$env_file" ] || { echo "尚未設定電腦操控（執行 scripts/enable-computer-control.sh）" >&2; exit 1; }
token="$(tr -d '\r' < "$env_file" | sed -n 's/^SIRO_COMPUTER_TOKEN=//p')"
base="http://127.0.0.1:${SIRO_GATEWAY_PORT:-8000}/v1/computer"
api() { curl -s -m15 -H "X-SIRO-Computer-Token: $token" -H 'content-type: application/json' "$@"; }

status="$(api "$base/status" || true)"
case "$status" in *'"enabled":true'*) ;; *) echo "電腦操控沒有開啟：請先在托盤選單開啟「電腦操控」。" >&2; exit 1;; esac
echo "請把遊戲視窗點到最前面；$delay 秒後開始（Ctrl+Alt+Shift+Esc 急停）。"
sleep "$delay"
body="$(python3 -c 'import json,sys; print(json.dumps({"goal": sys.argv[1][:500]}))' "$goal")"
api -X POST -d "$body" "$base/run"; echo
echo "開始。下面會即時印出每一步（長跑也不會等到結束才顯示）。"
python3 - "$base" "$token" <<'PY'
import json, sys, time, urllib.request

base, token = sys.argv[1], sys.argv[2]
printed = 0
last_phase = ""
segments_seen = 0

def get_status():
    req = urllib.request.Request(
        base + "/status",
        headers={"X-SIRO-Computer-Token": token},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)

# Wait until the run is actually marked running (or already finished).
for _ in range(30):
    d = get_status()
    if d.get("running") or d.get("report"):
        break
    time.sleep(0.5)

while True:
    d = get_status()
    phase = d.get("phase") or ""
    segs = int(d.get("session_segments") or 0)
    if segs > segments_seen:
        if segments_seen:
            print(f"— 第 {segs} 段 —", flush=True)
            printed = 0  # each segment starts a fresh live step list
        segments_seen = segs
    if phase and phase != last_phase and phase not in {"observing", "acting", "done", "stopped", "failed"}:
        # Show deciding/waiting so long model calls are visible.
        if phase in {"deciding", "waiting", "waiting_for_matching_screen"}:
            print(f"… {phase}", flush=True)
        last_phase = phase
    steps = d.get("live_steps") or []
    if not d.get("running"):
        steps = (d.get("report") or {}).get("steps") or steps
    while printed < len(steps):
        s = steps[printed]
        printed += 1
        seen = (s.get("seen") or "").strip() or "-"
        print(
            f'{s.get("step")} {s.get("action")} {s.get("outcome")} | 看到: {seen[:100]}',
            flush=True,
        )
    if not d.get("running"):
        r = d.get("report") or {}
        print(
            "結果:",
            r.get("state"),
            "|",
            str(r.get("reason") or "")[:200],
            "| 新增筆記:",
            d.get("learned_notes", "-"),
            flush=True,
        )
        break
    time.sleep(1.5)
PY
