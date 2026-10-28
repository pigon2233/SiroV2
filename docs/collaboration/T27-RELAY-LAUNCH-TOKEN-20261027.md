# T27 relay launch token continuity — 2026-10-27

- Task: preserve the private ESP32 HTTP relay token when the companion launcher starts the Gateway.
- Owner/session: Codex `/root`, current session; local-only work.
- Started: 2026-10-27 Asia/Taipei.
- Status: LOCAL_VERIFIED / LOCAL_ONLY / NOT PUSHED. The user handed over the active launcher; live integration is now running from this isolated worktree. Remote push and main-checkout merge remain unauthorized.
- Base SHA: `1ff57b2de9beb599007415a7051e018d5776f710` (main snapshot checked before edits).
- Branch: `codex/t27-relay-launch-secret-current`.
- Worktree: `E:\coding\Worktrees\t27-relay-launch-secret-current\SiroV2`.
- Owned paths: `scripts/start-companion`; `scripts/load-esp32-relay-token`; `tests/integration/test_esp32_companion_token.py`; `docs/ESP32_HTTP_INGRESS.md`; `docs/evidence/T27-relay-launch-2026-10-24/REPORT.md`; this file.
- Excluded paths: dirty main checkout changes, especially `desktop/host.js`; active service processes; shared `docs/STATUS.md`, `docs/TASKS.md`, `docs/DECISIONS.md`; secrets and private data.
- Dependency: none for the controlled local restart after the user's handoff. The main checkout remains dirty and is not modified.
- Acceptance: shell syntax; Ruff check/format; the token-loader and desktop-entry integration tests; later, after handoff, a controlled restart and fresh authenticated ESP32 ingress/World State evidence.
- Next step: keep the foreground Gateway session observable; if the user later authorizes a specific merge target, stop it gracefully, integrate the local commits, and repeat the hardware motion/button check. Do not push without explicit branch authorization.

## 本輪驗證（2026-10-27）

- `bash -n scripts/start-companion scripts/load-esp32-relay-token`: PASS (exit 0).
- `PYTHONPATH=src /home/pepepig/.venvs/sirov2/bin/python -m pytest -q tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS, 49 passed in 12.05s.
- `/home/pepepig/.venvs/sirov2/bin/ruff check tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS.
- `/home/pepepig/.venvs/sirov2/bin/ruff format --check tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py`: PASS, already formatted.
- `git diff --check`: PASS.
- Live read-only observation: Gateway PID 17789 is healthy on 127.0.0.1:8000 but its environment has no `SIRO_ESP32_RELAY_TOKEN`; 8765 remains listening as PID 50012. No restart or live mutation was performed because the other AI still owns the active launcher.
- Integration commit in this branch: `69d86ff` (cherry-picked local implementation `cccd49d3c0bfa95286be4e0258ae5b26111faaa7`).
- This branch remains LOCAL_ONLY / NOT PUSHED.

## 交接後 live 驗收（2026-10-27）

- User explicitly handed over the active launcher. The previous Gateway tree was stopped gracefully; Windows 8765 relay PID 50012 remained running.
- Successful Gateway PID 20351 runs from this worktree with the private token loader. `/health/live` returned 200; authenticated unknown-event probe returned 400, proving ingress was enabled and reached validation.
- Fresh World State rows from `device:siro-node-01:esp32_http` recorded illuminance 228.3 → 233.3 → 230.8 lux at 2026-10-26T16:41:02Z–16:42:02Z. See [`T27-esp32-live-2026-10-27`](../evidence/T27-esp32-live-2026-10-27/REPORT.md).
- A first restart attempt failed closed because `uv` created an E-drive `.venv` and missed readiness; the successful run used `/home/pepepig/.venvs/sirov2` via `UV_PROJECT_ENVIRONMENT` guidance.

## 接手（2026-10-28 Asia/Taipei）

- Claude 依使用者指示接手 Codex 的 T27 ESP32 工作（分支 `codex/t27-esp32-sensor-telemetry`、`codex/t27-http-event-ingress`、本分支）；仍沿用本 worktree，LOCAL_ONLY／NOT PUSHED，不 push、不改 PR。
- 唯讀核對：8000 Gateway 與 8765 relay 皆在監聽；d4ed0cd 只在本分支，未進 main。
- 待辦：PIR 與按鈕經新流程實機驗收（需使用者在板子前操作）；整合到 main 需使用者另行指定目標；MQTT 韌體未刷板；兩個 Draft PR 的 CI 失敗源自 main 既有格式問題。

## 使用者驗收回報（2026-10-28 Asia/Taipei）

- 使用者表示 PIR 與按鈕都已確認沒問題，不需再測。此為使用者口頭回報，我沒有獨立讀到 SIRO 端的 motion／按鈕事件，故 PIR／按鈕記為 OWNER-REPORTED，不是自動化證據。
- Gateway 與 8765 中繼的整合已在本分支（含 `569ef0c` HTTP 入口）；光度已有 live World State 證據。
- 剩餘：合併到 main 的目標與時機由使用者決定；MQTT 版韌體未刷板；PR #3／#4 的 CI 失敗源自 main 既有格式問題。全部 LOCAL_ONLY／NOT PUSHED。
