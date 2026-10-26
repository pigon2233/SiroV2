# T27 relay launch token continuity — 2026-10-27

- Task: preserve the private ESP32 HTTP relay token when the companion launcher starts the Gateway.
- Owner/session: Codex `/root`, current session; local-only work.
- Started: 2026-10-27 Asia/Taipei.
- Status: PARTIAL / LOCAL_ONLY / NOT PUSHED. Runtime integration is blocked while another AI owns the active SIRO/VRM launcher and service.
- Base SHA: `1ff57b2de9beb599007415a7051e018d5776f710` (main snapshot checked before edits).
- Branch: `codex/t27-relay-launch-secret-current`.
- Worktree: `E:\coding\Worktrees\t27-relay-launch-secret-current\SiroV2`.
- Owned paths: `scripts/start-companion`; `scripts/load-esp32-relay-token`; `tests/integration/test_esp32_companion_token.py`; `docs/ESP32_HTTP_INGRESS.md`; `docs/evidence/T27-relay-launch-2026-10-24/REPORT.md`; this file.
- Excluded paths: dirty main checkout changes, especially `desktop/host.js`; active service processes; shared `docs/STATUS.md`, `docs/TASKS.md`, `docs/DECISIONS.md`; secrets and private data.
- Dependency: explicit handoff from the other AI before integrating or restarting the live Gateway; no service mutation is authorized in this turn.
- Acceptance: shell syntax; Ruff check/format; the token-loader and desktop-entry integration tests; later, after handoff, a controlled restart and fresh authenticated ESP32 ingress/World State evidence.
- Next step: cherry-pick local implementation commit `cccd49d3c0bfa95286be4e0258ae5b26111faaa7` into this isolated branch, run the stated tests, then hand off the commit. Do not push.
