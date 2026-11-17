#!/usr/bin/env bash
# Fine-tune MeloTTS on the SIRO corpus (WSL, ~/.venvs/melotts only).
#
#   bash scripts/tts_train/train_siro.sh            # foreground, auto-resume loop
#   nohup bash scripts/tts_train/train_siro.sh >/dev/null 2>&1 &
#
# Needs melotts-train.patch applied to ~/tts-train/MeloTTS (see HANDOFF-DIARY).
# Checkpoints + train.log go to ~/tts-train/runs/$RUN_NAME. Re-running resumes
# from the newest G_/D_/DUR_ checkpoint there. Env overrides below.
set -u

RUN_NAME=${RUN_NAME:-siro-sweet-b-v1}
DATA=${DATA:-$HOME/tts-train/data/siro-sweet-b-v1}
MELO=${MELO:-$HOME/tts-train/MeloTTS/melo}
PY=${PY:-$HOME/.venvs/melotts/bin/python}
PRETRAIN_G=${PRETRAIN_G:-$HOME/tts-train/pretrained/zh-remapped/G_0.pth}
BATCH=${BATCH:-4}
FP16=${FP16:-false}   # true crashes: NaN -> empty tensor in the SDP spline (2026-11-17)
TARGET_STEPS=${TARGET_STEPS:-20000}
LOG_INTERVAL=${LOG_INTERVAL:-50}
EVAL_INTERVAL=${EVAL_INTERVAL:-1000}
KEEP=${KEEP:-3}
WORKERS=${WORKERS:-4}
PORT=${PORT:-10902}

RUN=$HOME/tts-train/runs/$RUN_NAME
mkdir -p "$RUN" "$MELO/logs"
# train.py always writes to ./logs/<model>; point that at the run folder.
[ -e "$MELO/logs/$RUN_NAME" ] || ln -s "$RUN" "$MELO/logs/$RUN_NAME"

"$PY" - "$DATA/config.json" "$RUN/train_config.json" <<PY
import json, math, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
t = cfg["train"]
n_train = sum(1 for _ in open(cfg["data"]["training_files"], encoding="utf-8"))
t.update(batch_size=$BATCH, fp16_run=("$FP16" == "true"), log_interval=$LOG_INTERVAL,
         eval_interval=$EVAL_INTERVAL, keep_ckpts=$KEEP, num_workers=$WORKERS)
t["epochs"] = math.ceil($TARGET_STEPS / max(1, n_train // $BATCH))
json.dump(cfg, open(sys.argv[2], "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print(f"train={n_train} batch={t['batch_size']} fp16={t['fp16_run']} epochs={t['epochs']}")
PY

cd "$MELO" || exit 1
# train.py's own logger writes losses to $RUN/train.log; stdout/stderr go to console.log.
while :; do
  echo "=== start $(date -Is)" >> "$RUN/console.log"
  "$(dirname "$PY")/torchrun" --nproc_per_node=1 --master_port="$PORT" \
    train.py --c "$RUN/train_config.json" --model "$RUN_NAME" --pretrain_G "$PRETRAIN_G" \
    >> "$RUN/console.log" 2>&1
  code=$?
  echo "=== exit $code $(date -Is)" >> "$RUN/console.log"
  [ "$code" -eq 0 ] && break
  [ -e "$RUN/STOP" ] && break   # touch $RUN/STOP to keep it from restarting
  sleep 30
done
