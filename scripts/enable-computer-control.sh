#!/usr/bin/env bash
# Owner-run switch for SIRO desktop control (default: off). Run in WSL:
#   bash scripts/enable-computer-control.sh            # set up (idempotent)
#   bash scripts/enable-computer-control.sh --disable  # remove the config file (feature off again)
# It writes %USERPROFILE%\siro-computer\computer.env (token, allowed programs, cloud-screen consent)
# and makes the backend launcher read it. The Windows pet reads the same file. Backup: <launcher>.prev-computer
set -euo pipefail
launcher="$HOME/.local/bin/siro-companion-vrm"
win_home="$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')")"
dir="$win_home/siro-computer"
env_file="$dir/computer.env"

if [ "${1:-}" = "--disable" ]; then
  rm -f "$env_file"
  echo "Removed $env_file. Restart SIRO; desktop control is off (launcher line is harmless without the file)."
  exit 0
fi

mkdir -p "$dir"
if [ ! -f "$env_file" ]; then
  umask 077
  cat > "$env_file" <<EOF
# SIRO desktop control. Delete this file (or run enable-computer-control.sh --disable) to turn it off.
# Read by the WSL backend launcher and by the Windows pet.
SIRO_COMPUTER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
# Programs SIRO may control (comma separated, lowercase process names). Empty = nothing.
SIRO_COMPUTER_ALLOWED_PROCESSES=undertale.exe
# 1 = the foreground window's screenshot may be sent to the cloud model (Claude CLI). 0 = refuse to send.
SIRO_COMPUTER_CLOUD_SCREEN=1
# 1 = keep playing without stopping to ask the owner (ask→wait; low-confidence act still runs).
SIRO_COMPUTER_AUTONOMOUS=1
# 1 = after a recoverable stop, start another segment with the same goal (until e-stop).
SIRO_COMPUTER_ENDLESS=1
# 0 = no step/time/segment cap while endless+autonomous (owner e-stop still stops).
SIRO_COMPUTER_MAX_STEPS=0
SIRO_COMPUTER_MAX_SECONDS=0
SIRO_COMPUTER_MAX_SEGMENTS=0
# Decision brain: ollama (local vision, default) or claude (cloud CLI).
SIRO_COMPUTER_DECIDER=ollama
SIRO_COMPUTER_OLLAMA_MODEL=gemma4:e4b
# Skip post-run Claude reflection while iterating on play speed.
SIRO_COMPUTER_PLAYBOOK=0
# Optional residual click fix after DPI/multi-monitor map: ox,oy,sx,sy (default identity).
# SIRO_COMPUTER_COORD_CALIB=0,0,1,1
EOF
  echo "Created $env_file (edit SIRO_COMPUTER_ALLOWED_PROCESSES to choose games)."
fi

if grep -q 'siro-computer/computer.env' "$launcher"; then
  echo "Launcher already reads the file."
else
  cp -p "$launcher" "$launcher.prev-computer"
  python3 - "$launcher" "$env_file" <<'PY'
import sys
path, env_file = sys.argv[1], sys.argv[2]
text = open(path).read()
marker = 'cd "$checkout"\nsystemctl --user start ollama.service'
if marker not in text:
    sys.exit("launcher layout changed; add the sourcing block by hand (see docs/agent/COMPUTER-USE-RUNBOOK.md)")
block = (
    "# Desktop control: only when the owner created this file (default off). CRLF-tolerant.\n"
    f'computer_env="{env_file}"\n'
    'if [ -f "$computer_env" ]; then\n'
    "  # shellcheck disable=SC1090\n"
    "  set -a; . <(tr -d '\\r' < \"$computer_env\"); set +a\n"
    "fi\n"
)
open(path, "w").write(text.replace(marker, block + marker))
PY
  bash -n "$launcher"
  echo "Launcher updated (backup: $launcher.prev-computer)."
fi
echo "Next: restart SIRO (Stop-SIRO-Win.cmd then Start-SIRO-VRM-Win.cmd), then tray -> 電腦操控 -> on."
