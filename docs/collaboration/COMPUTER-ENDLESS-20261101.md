# COMPUTER-ENDLESS-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Continues branch `codex/computer-autonomous-20261101` at `E:/coding/Worktrees/computer-autonomous-20261101`.
- Goal: endless autonomous play — on loss click continue once; no step/time/segment caps that only halt play; faster decisions.
- Owned: `src/siro/services/computer_use/{http,decision,loop}.py`, `desktop-win/computer-perception.js`, related tests, `scripts/enable-computer-control.sh`, owner `computer.env`, this handoff.
- Exclusions: dirty design files on main, shared STATUS, game Reset, recording owner play.

## Result

- Autonomous prompt: on defeat/death/game over/retry/continue, click once and keep a new run; do not answer `done` just because a run ended.
- Endless + autonomous: `SIRO_COMPUTER_MAX_STEPS/SECONDS/SEGMENTS=0` (or unset/`unlimited`) → no caps. Soft stops (stuck wait / no-change / invalid / model `done`) keep going instead of ending the session.
- Speed: shorter settle/wait (0.15/0.35s), history last 5, Claude timeout 55s, faster transient retries, segment gap 0.4s, screenshot max width 960.
- Safety unchanged: e-stop, allowlist, secrets, unknown no-resend, tray disable.
- Tests: loop + http computer-use (see latest run). Live checkout must be synced; **restart SIRO** + tray re-enable required.

## Owner stop

- Tray disable or `Ctrl+Alt+Shift+Esc`.
