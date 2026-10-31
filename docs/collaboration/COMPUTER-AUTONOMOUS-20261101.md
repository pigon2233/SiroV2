# COMPUTER-AUTONOMOUS-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Base: `591e1c55b3062fe516bea20280a02091a8c5e9da`
- Branch: `codex/computer-autonomous-20261101`
- Worktree: `E:/coding/Worktrees/computer-autonomous-20261101`
- Goal: owner does not want computer-use to stop and ask; keep inferring / trying within existing hard safety gates.
- Owned paths: `src/siro/services/computer_use/loop.py`, `src/siro/services/computer_use/decision.py`, `scripts/enable-computer-control.sh`, `tests/unit/test_computer_use_loop.py`, this handoff. Owner `computer.env` gained `SIRO_COMPUTER_AUTONOMOUS=1`.
- Exclusions: main checkout dirty design files, shared STATUS, game saves, recording owner play.
- Acceptance: with flag on, `ask` and low-confidence `act` do not stop as `needs_owner` / `low_confidence`; flag-off keeps prior stops; unit tests cover both; emergency stop / allowlist / unknown outcome unchanged.

## Result

- Opt-in `SIRO_COMPUTER_AUTONOMOUS=1`:
  - `ask` → treated as `wait` (no `needs_owner` stop)
  - low-confidence `act` → still executed
  - low-confidence non-act → `wait`
  - Prompt/task text tells the model not to ask when autonomous
- Default (flag off / tests): previous `needs_owner` and `low_confidence` stops remain.
- Hard gates unchanged: emergency stop, allowlist, secret fields, unknown outcome, stuck, step/time limits.
- Owner `computer.env` updated with `SIRO_COMPUTER_AUTONOMOUS=1` (token not printed). **Restart SIRO** so the gateway process loads the flag.
- Tests: `PYTHONPATH=src ... pytest -q tests/unit/test_computer_use_loop.py` → **63 passed**.
- Source also copied into the live Windows checkout (`SiroV2`) so the companion launcher can load it after restart. Worktree remains the task branch.
- Not done: auto-requeue longplay goals, local weight training, lowering cloud latency. Commit pending owner request (LOCAL_ONLY).

## Next

- Restart SIRO, keep tray control on, run a bounded STS2 session and confirm status `limits.autonomous` is true and runs no longer end in `needs_owner` / immediate `low_confidence` without a wait/act attempt.
- Optional later: raise `SIRO_COMPUTER_MAX_STEPS` / `MAX_SECONDS` for longer continuous play.
