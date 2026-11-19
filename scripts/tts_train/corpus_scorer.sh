#!/usr/bin/env bash
# Run corpus_scorer.py in ~/.venvs/corpus-scorer with the environment it needs:
# Linux-only PATH (WSL's Windows ffmpeg cannot run) and the venv's CUDA libs.
V=${SCORER_VENV:-$HOME/.venvs/corpus-scorer}
NV=$V/lib/python3.10/site-packages/nvidia
export PATH=$V/bin:/usr/local/bin:/usr/bin:/bin
export LD_LIBRARY_PATH=$NV/cublas/lib:$NV/cudnn/lib:${LD_LIBRARY_PATH:-}
HERE=$(dirname "$(readlink -f "$0")")
cd /tmp && exec "$V/bin/python" "$HERE/${SCORER_SCRIPT:-corpus_scorer.py}" "$@"
