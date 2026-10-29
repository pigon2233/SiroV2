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
sleep 3
until api "$base/status" | grep -q '"running":false'; do sleep 4; done
api "$base/status" | python3 -c '
import sys, json
d = json.load(sys.stdin); r = d["report"]
print("結果:", r["state"], "|", r["reason"][:200], "| 新增筆記:", d.get("learned_notes", "-"))
for s in r["steps"]:
    print(s["step"], s["action"], s["outcome"], "| 看到:", s.get("seen", "")[:80])
'
