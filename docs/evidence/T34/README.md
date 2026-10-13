# T34 驗收證據

日期：2026-09-26｜結果：PASS（L1 + Linux L2 clean-environment A22）

`siro backup --data DATA DESTINATION` 與 `siro restore --data DATA BACKUP` 使用一致 SQLite backup/restore，
還原會先建立不存在的目標資料目錄、做 integrity check 並套用當前 migration。整合測試從全新 data directory
啟動 demo、備份，再還原到第二個不存在的新 data directory，資料庫完整性為 `ok`。

`scripts/start PID_FILE`、`scripts/stop PID_FILE`、`scripts/backup`、`scripts/restore` 提供統一入口；start
建立並在退出時清除 PID file，stop 只接受明確 PID file，不以 process-name 廣泛終止。完整 `scripts/check`：Python 128 passed、5 external opt-in skipped；
Rust 6 passed。

全面稽核後補齊：

- `scripts/install` 以 `uv sync --project … --locked --no-dev` 從無 `.venv` 的乾淨 source 建立 production
  environment，產生 loopback `siro-gateway.service` 與 daily log-prune timer；預設不自動 enable。
- `scripts/doctor` 提供固定診斷入口；三個 units 以本機 `systemd-analyze verify` 通過。
- gateway 以每日 rotated file log 加 14-day retention；shutdown 將 health 設為 `draining`、將 active turns
  標成 `interrupted_shutdown`、呼叫 cancel 並關閉連線。
- 帶 config 的 backup 為含 SHA-256 manifest 的 ZIP；restore 先驗 hash、設定 schema 與 SQLite integrity，
  可從全新目錄恢復 identity/memory DB 及設定，tampered bundle 會拒絕。
- Linux L2 使用全新 `/tmp/siro-t34-clean-rnloCI` source/venv/XDG 目錄完成 locked install、doctor 與 unit
  verify；另以 port 18765 啟動真 Uvicorn、讀取 `/health/ready`、備份／還原、SIGTERM stop 並確認 PID
  file 清除。第一次演練發現 `kill --signal TERM` 不相容 Bash builtin，已修成 `kill -TERM` 後重跑通過。

24-hour soak 屬 T35，不列入 T34 完成條件。

最終完整 `scripts/check`：Rust 6 passed；Python 138 passed、5 個 external provider opt-in skipped；Ruff、
Mypy、format、schema 與 secret scan 全部通過。唯一 warning 為 Starlette TestClient 對 httpx 的上游棄用
提示，不影響 runtime gate。
