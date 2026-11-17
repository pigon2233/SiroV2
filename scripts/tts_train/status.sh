#!/usr/bin/env bash
# Show MeloTTS training progress: bash scripts/tts_train/status.sh [run-name]
RUN=$HOME/tts-train/runs/${1:-siro-sweet-b-v1}
LOG=$RUN/train.log
echo "run: $RUN"
if pgrep -f "train.py --c $RUN/" >/dev/null; then echo "process: running"; else echo "process: NOT running"; fi
# train.py logs "[loss_disc, loss_gen, loss_fm, loss_mel, loss_dur, loss_kl, step, lr]"
last=$(grep -E "^\S.*INFO.*\[[0-9.e+-]+, " "$LOG" 2>/dev/null | tail -1)
if [ -n "$last" ]; then
  echo "last log line: $last" | cut -c1-220
  python3 - "$LOG" <<'PY'
import re, sys
from datetime import datetime
rows = []
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    m = re.search(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*\[([^\]]+)\]\s*$", line)
    if m and "INFO" in line:
        try:
            vals = [float(v) for v in m.group(2).split(",")]
        except ValueError:  # e.g. "Train Epoch: 1 [0%]"
            continue
        if len(vals) >= 8:
            rows.append((datetime.fromisoformat(m.group(1)), int(vals[6]), vals))
if rows:
    t, step, v = rows[-1]
    print(f"step {step}  disc {v[0]:.3f} gen {v[1]:.3f} fm {v[2]:.3f} mel {v[3]:.3f} dur {v[4]:.3f} kl {v[5]:.3f}")
    if len(rows) >= 2:
        (t0, s0, _), (t1, s1, _) = rows[max(0, len(rows) - 6)], rows[-1]
        if s1 > s0:
            sec = (t1 - t0).total_seconds() / (s1 - s0)
            print(f"speed ~{sec:.2f} s/step; 20000 steps left: ~{max(0, 20000 - s1) * sec / 3600:.1f} h")
PY
else
  echo "no loss lines yet"; tail -5 "$LOG" 2>/dev/null
fi
echo "latest checkpoint: $(ls -t "$RUN"/G_*.pth 2>/dev/null | head -1)"
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader
