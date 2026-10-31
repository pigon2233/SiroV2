# COMPUTER-ENDLESS-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Continues branch `codex/computer-autonomous-20261101` at `E:/coding/Worktrees/computer-autonomous-20261101`.
- Goal: long autonomous sessions — high per-segment limits, Claude decision retries, auto-continue after recoverable stops.
- Owned: `src/siro/services/computer_use/{http,decision,loop}.py`, related tests, `scripts/enable-computer-control.sh`, owner `computer.env`, this handoff.
- Exclusions: dirty design files on main, shared STATUS, game Reset, recording owner play.

## Result

- Per segment: up to 1200 steps / 7200 s (owner env).
- `SIRO_COMPUTER_ENDLESS=1` + autonomous: after recoverable ends (`step_limit`, `time_limit`, `decider_error:*`, `done`, stuck waits, etc.) start another segment with the same goal; stop on emergency stop, control off, privacy/unknown/window denials, or `SIRO_COMPUTER_MAX_SEGMENTS` (default 48, max 500).
- Claude CLI transient failures (`claude_failed` / `claude_error` / `claude_bad_output`) retry up to 3 attempts with backoff before failing the segment.
- Tests: loop + http + perception computer-use → **99 passed** (1 Starlette deprecation warning).
- Live checkout synced; **restart SIRO** required. `Play-SIRO.cmd` waits until the whole session ends (can be many hours).

## Owner stop

- Tray disable or `Ctrl+Alt+Shift+Esc`.
