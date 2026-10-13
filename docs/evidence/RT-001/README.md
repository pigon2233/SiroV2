# RT-001 baseline verification

2026-10-01。既有 dirty tree 保留；本卡只改測試與文件，未改 production/migrations。

- 修正空 DB 測試：版本與 bundled migrations 對照，仍驗 WAL、foreign keys、integrity。
- 新增真 migration 0/10/12→目前 schema 案例：保留 identity 資料；migration checksum/applied timestamp 重跑不變；tool/run tables、indexes、agent_steps columns/FK 有具體 assertions。
- 新增正式 `.venv/bin/siro-gateway` 子程序 smoke：移除 SIRO provider env，隔離 tmp data、隨機 loopback port；健康與首頁 HTTP 成功；SIGTERM 後確認 application shutdown complete，finally 回收程序。未呼叫 cloud/TTS/hardware。
- 初次 smoke 失敗：假設 graceful shutdown 必須 exit 0。實際 Uvicorn 完成 shutdown 後 return -SIGTERM；測試改驗 exit 0/-SIGTERM 且必須有 shutdown complete，沒有放寬到任意非零。

最後命令：`uv run pytest -q && uv run mypy && uv run ruff check src tests`
結果：exit 0；198 passed、5 skipped、3 warnings，19.52s；mypy 164 source files 通過；ruff 通過。
5 skipped 仍是 opt-in 真 provider/speech；不算真服務成功。未更動 Rust，沿用 Phase 1 Rust 6 tests 證據，不宣稱本次重跑。

Rollback：撤回本卡兩個測試檔變更與文件記錄；資料 schema 無變更。
下一卡：RT-002 原生工具訊息接入。
