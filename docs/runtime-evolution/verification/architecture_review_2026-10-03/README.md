# Architecture review evidence — 2026-10-03

主報告：[ARCHITECTURE_REVIEW.md](../../ARCHITECTURE_REVIEW.md)。檢查工作區，HEAD a27001d；RT-008 十個完成 digest 全部吻合。本目錄 source-digests.json 保存本次 Python source 與相關 RT-008 檔案指紋。

本次命令與結果：

| Command（SiroV2 根目錄） | Result |
|---|---|
| `uv run pytest -q` | exit 0；285 passed、5 skipped、3 dependency warnings，52.53s |
| `uv run ruff check src tests` | exit 0；All checks passed |
| `uv run mypy` | exit 0；174 source files PASS |
| `uv run python docs/runtime-evolution/verification/architecture_review_2026-10-03/probe.py` | exit 0；反例確認，輸出見 probe-result.json |

五個 skipped 是原 opt-in model/speech provider cases，不算真服務驗收。未重跑 Rust、GPU、GUI、硬體或部署 rollback。

probe.py 使用 TemporaryDirectory、合成模型、真 controller/Core/SQLite、list 副作用，不使用 private runtime data／外部 provider／桌面動作。它斷言目前缺陷能重現；exit 0 **不是 acceptance 成功**。初次 probe 預期 restart 時觸發 journal ownership ValueError，實際先觸發既有 tool_proposals unique constraint 的 IntegrityError；已依觀測修正探針，沒有修改 production。主報告明確區分此既有約束與 RT-008 新 ownership 耦合。

反例包括同 session 的不同 run 重用 call ID、restart 後持久 key collision、provider failure 後仍 dispatch／最終 completed、arguments-only executor 在 cancelled terminal 後執行。另保存 terminal 後 retained map 計數；這不是 RSS／soak 測量。

後續修補應把 desired behavior 寫入正式 tests，不能把本探針的 defect assertions 當成功規格。標準 pytest 不會收集此文件目錄。
