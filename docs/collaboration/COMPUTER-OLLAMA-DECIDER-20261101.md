# COMPUTER-OLLAMA-DECIDER-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Continues computer-autonomous work on main live checkout + worktree `computer-autonomous-20261101`.
- Goal: stop using Claude for computer-use decisions; use local Ollama vision (`gemma4:e4b`).
- Owned: `src/siro/services/computer_use/decision.py`, `http.py`, tests, `scripts/enable-computer-control.sh`, owner `computer.env`, this handoff.
- Exclusions: shared STATUS, Claude auth repair, game Reset.

## Result

- Default decider is `OllamaVisionDecider` (`SIRO_COMPUTER_DECIDER=ollama`).
- Screenshots stay local via Ollama `/api/chat` + `images`; `think=false` for speed.
- `SIRO_COMPUTER_DECIDER=claude` still selects the old Claude CLI path.
- Owner env set to ollama + `gemma4:e4b`; playbook off.
- Tests: `test_computer_use_ollama_decider.py` + http → 12 passed.
- **Restart SIRO** required; tray enable + STS2 focused before play.
