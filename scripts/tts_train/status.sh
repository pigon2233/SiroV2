#!/usr/bin/env bash
# MeloTTS 訓練進度（文字版）：bash scripts/tts_train/status.sh [run-name]
exec python3 "$(dirname "$0")/training_status.py" --run "$HOME/tts-train/runs/${1:-siro-sweet-b-v1}"
