#!/usr/bin/env bash
# Ask SIRO to play/operate a program on this PC. Usage (WSL):
#   bash scripts/computer-play.sh "goal in your own words" [seconds_before_start=20]
# You get the delay to click the game window to the front (talking to SIRO takes the focus away).
# She only acts while the foreground program is on the allowed list in siro-computer/computer.env,
# and control must be switched on from the tray. Emergency stop: Ctrl+Alt+Shift+Esc.
# Ctrl+C also POSTs /v1/computer/stop so the backend run ends with the console.
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

stop_run() {
  api -X POST "$base/stop" >/dev/null 2>&1 || true
  echo "已送出停止（/v1/computer/stop）。" >&2
}
trap 'stop_run; exit 130' INT TERM

status="$(api "$base/status" || true)"
# Optional fail-closed source identity check BEFORE countdown or any /run POST.
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
printf '%s' "$status" | python3 "$project_root/scripts/computer_runtime_check.py" --expected "$project_root" --config "$env_file"
case "$status" in *'"enabled":true'*) ;; *) echo "電腦操控沒有開啟：請先在托盤選單開啟「電腦操控」。" >&2; exit 1;; esac
echo "請把遊戲視窗點到最前面；$delay 秒後開始（Ctrl+C 停止；Ctrl+Alt+Shift+Esc 急停）。"
sleep "$delay"
body="$(python3 -c 'import json,sys; print(json.dumps({"goal": sys.argv[1][:500]}))' "$goal")"
api -X POST -d "$body" "$base/run"; echo
echo "開始。下面會即時印出每一步（長跑也不會等到結束才顯示）。"
python3 - "$base" "$token" <<'PY'
import json, signal, sys, time, urllib.request

base, token = sys.argv[1], sys.argv[2]
printed = 0
last_phase = ""
segments_seen = 0
ends_seen = 0
stopping = False

def post_stop(*_args):
    global stopping
    if stopping:
        return
    stopping = True
    req = urllib.request.Request(
        base + "/stop",
        data=b"{}",
        method="POST",
        headers={"X-SIRO-Computer-Token": token, "content-type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except Exception:
        pass
    print("已送出停止（/v1/computer/stop）。", flush=True)
    raise SystemExit(130)

signal.signal(signal.SIGINT, post_stop)
signal.signal(signal.SIGTERM, post_stop)

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
    ends = d.get("segment_ends") or []
    while ends_seen < len(ends):
        e = ends[ends_seen]
        ends_seen += 1
        detail = str(e.get("detail") or "").strip()
        extra = f" | {detail[:160]}" if detail else ""
        print(
            f"— 第 {e.get('segment')} 段結束: {e.get('state')}/{e.get('reason')}{extra} —",
            flush=True,
        )
    segs = int(d.get("session_segments") or 0)
    if segs > segments_seen:
        if segments_seen:
            print(f"— 第 {segs} 段開始 —", flush=True)
            printed = 0  # each segment starts a fresh live step list
        else:
            print(f"— 第 {segs} 段開始 —", flush=True)
        segments_seen = segs
    if phase and phase != last_phase and phase not in {"observing", "acting", "done", "stopped", "failed"}:
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
        scene = (s.get("scene") or "").strip()
        detail = s.get("detail")
        detail = "" if detail is None else str(detail).strip()
        if detail in {"None", "null"}:
            detail = ""
        extra = ""
        if scene:
            extra += f" | 場景:{scene}"
        if detail:
            extra += f" | {detail[:160]}"
        print(
            f'{s.get("step")} {s.get("action")} {s.get("outcome")} | 看到: {seen[:100]}{extra}',
            flush=True,
        )
    if not d.get("running"):
        r = d.get("report") or {}
        print(
            "結果:",
            r.get("state"),
            "|",
            str(r.get("reason") or "")[:200],
            "|",
            str(r.get("detail") or "")[:200],
            "| 新增筆記:",
            d.get("learned_notes", "-"),
            flush=True,
        )
        break
    time.sleep(1.5)
PY
