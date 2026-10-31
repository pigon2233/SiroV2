#!/usr/bin/env bash
set -euo pipefail
env_file=/mnt/c/Users/pepepig/siro-computer/computer.env
file "$env_file"
od -An -tx1 -N8 "$env_file"
echo "---raw---"
cat -A "$env_file"
echo "---source---"
set -a
. <(tr -d '\r' < "$env_file")
set +a
echo "TOKEN_LEN=${#SIRO_COMPUTER_TOKEN}"
echo "AUTONOMOUS=${SIRO_COMPUTER_AUTONOMOUS-}"
echo "MAX_STEPS=${SIRO_COMPUTER_MAX_STEPS-}"
echo "ENDLESS=${SIRO_COMPUTER_ENDLESS-}"
