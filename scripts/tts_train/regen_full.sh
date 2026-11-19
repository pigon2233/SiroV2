#!/usr/bin/env bash
# Full v2 regeneration: plan -> Qwen generation -> scoring. Resumable; run detached:
#   setsid nohup bash scripts/tts_train/regen_full.sh > /dev/null 2>&1 < /dev/null &
# Log: <out>/run.log. SIRO must be stopped (shares the GPU). Scoring runs after
# generation so Qwen and the scoring models never share the 8 GB GPU.
set -u
S=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-$HOME/.local/share/siro/tts-corpus/siro-sweet-b-v2}
D=$HOME/.local/share/siro/data
mkdir -p "$OUT"
exec >> "$OUT/run.log" 2>&1
echo "=== start $(date -Is)"
[ -f "$OUT/plan.json" ] || "$HOME/.venvs/corpus-scorer/bin/python" "$S/full_plan.py" --out "$OUT" || exit 1
ln -sfn "$OUT" "$HOME/tts-train/data/siro-regen"   # the corpus monitor page reads this
"$D/qwen-tts-venv/bin/python" "$S/trial_generate.py" --plan "$OUT/plan.json" \
  --model "$D/models/qwen3-tts-0.6b-base" --voice-profile "$D/voices/siro-sweet-b-v1.json" \
  --temperature 0.65 --top-k 30 || { echo "=== generate failed $(date -Is)"; exit 1; }
echo "=== generated $(date -Is)"
SCORER_SCRIPT=trial_score.py bash "$S/corpus_scorer.sh" "$OUT" --workers "$(( $(nproc) / 2 ))" \
  || { echo "=== score failed $(date -Is)"; exit 1; }
PAGES="$(wslpath "$(cmd.exe /c 'echo %LOCALAPPDATA%' 2>/dev/null | tr -d '\r')")/siro-corpus"
python3 "$S/spot_plan.py" --out "$OUT" && python3 "$S/build_trial_page.py" --trial "$OUT" \
  --plan "$OUT/spot_plan.json" --page-name spot.html --title "SIRO 語料抽聽" --page-dir "$PAGES"
echo "=== done $(date -Is)"
