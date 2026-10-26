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

## 本輪驗證（2026-10-27）

- `bash -n scripts/start-companion scripts/load-esp32-relay-token`: PASS (exit 0).
- `PYTHONPATH=src /home/pepepig/.venvs/sirov2/bin/python -m pytest -q tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS, 49 passed in 12.05s.
- `/home/pepepig/.venvs/sirov2/bin/ruff check tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS.
- `/home/pepepig/.venvs/sirov2/bin/ruff format --check tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS, already formatted.
- `git diff --check`: PASS.
- Live read-only observation: Gateway PID 17789 is healthy on 127.0.0.1:8000 but its environment has no `SIRO_ESP32_RELAY_TOKEN`; 8765 remains listening as PID 50012. No restart or live mutation was performed because the other AI still owns the active launcher.
- Integration commit in this branch: `69d86ff` (cherry-picked local implementation `cccd49d3c0bfa95286be4e0258ae5b26111faaa7`).
- This branch remains LOCAL_ONLY / NOT PUSHED.
