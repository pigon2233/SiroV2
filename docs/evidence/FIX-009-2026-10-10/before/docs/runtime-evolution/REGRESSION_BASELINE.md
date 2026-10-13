# Regression baseline

## 2026-10-10 incremental baseline

RI-002後716PASS；FIX-002後767PASS／5 real_provider未選／3既有warnings，111.45s。新增51 case覆蓋typed reason/native/legacy、malformed URL零dispatch、真scope/partial/origin reset、UI與owned teardown；不是搜尋網站或自主研究通過。真Bing與DDG有native roundtrip，但無搜尋結果，間歇public cleanup原因UNKNOWN。

[實際證據](../evidence/FIX-002-2026-10-10/REPORT.md)。


## Current baseline — 2026-10-09 Runtime Intelligence review

基準 main / `c1d2d41` 加本輪開始前既有未提交工作；保留文字／語音／Live2D成果。下方2026-09-30失敗紀錄是歷史，不再代表目前migration／Rust／session／工具能力狀態。現況及分層驗證見 [CURRENT_ARCHITECTURE_AUDIT](CURRENT_ARCHITECTURE_AUDIT.md) 與 [ROADMAP_RECONCILIATION](ROADMAP_RECONCILIATION.md)。

| 本輪實際命令／檢查 | 結果 | 有效範圍 |
|---|---|---|
| `.venv/bin/pytest -q -m "not real_provider"` 修改前 | 671 passed／5 deselected／3既有warnings，156.91s | 既有dirty tree離線基線；不是全產品驗收 |
| 同命令，最後修改後 | 701 passed／5 deselected／3既有warnings，147.01s | 新增30個開發工具fixtures；不把before/after耗時當效能收益 |
| `.venv/bin/pytest -q tests/test_codebase_memory.py` | 30 passed | source排除／symlink／大小限制／stale／sandbox與env；包含於701，不重複相加 |
| Linux bubblewrap合成隔離probe | 12項PASS | 精確helper版本：host home不可見、source/release只讀、無網路、cache可寫；不是production PatchVerifier已隔離 |
| Ruff format/check／mypy／schema check | PASS；269格式檔、204 source files | 本機格式／lint／types／export_schemas --check；不是遠端CI |
| `cargo test --workspace --locked` | 6 library tests PASS | 既有Rust元件回歸；不是全PC／硬體實機驗收 |
| developer config停用／恢復、6檔temp reverse/reapply | PASS，SHA復原 | 不回退原有dirty source；不需重啟SIRO |
| `/health/live`、`/`、`/live2d/` | HTTP200 | readiness；未以此替代真人對話／WebGL／人耳驗收 |

新增基線只覆蓋開發期Codebase Memory整合：索引無私人資料、啟動時拒絕過期source、禁止mutation、無網路／只讀mount、缺sandbox不降級到host。已連線MCP是快照，改source後須斷開及手動重索引。production既有251個source/tests/locks SHA零變。

本輪安全反例確認FIX-007／008／009及untrusted-check OS隔離、launcher activation／最新資料回退缺口；未修前不能用上述綠燈解禁skill generation或自動部署。測試盲區仍含真provider／新GPU／人耳／真人Live2D／真HA與ESP32／第二節點／24h soak／遠端CI／attestation；原FIX-005產品語音品質仍PARTIAL。完整命令／logs／rollback見 [本輪REPORT](../evidence/runtime-intelligence-2026-10-09/REPORT.md)。

## Historical baseline — 2026-09-30

日期 2026-09-30；目前 dirty working tree。定義「正常」必須限定路徑與測試層級，不接受全部綠燈或全功能完成的籠統說法。

## 本次實際執行

| 命令 | 結果 | 層級與限制 |
|---|---|---|
| `uv run pytest -q` | exit 1：193 passed、1 failed、5 skipped，20.62s | unit/contract/integration；包含 mock/simulator；不是全部 main E2E |
| `cargo test --workspace --locked` | exit 0：6 passed | local runtime/driver tests；不代表 Gateway uses Rust |
| `uv run ruff check src tests` | exit 0 | lint |
| `uv run mypy` | exit 0：163 source files | type checking |
| `curl -fsS --max-time 3 http://127.0.0.1:8000/health/live` | exit 7，connection refused | 目前 port 8000 無回應；不推定所有 SIRO 程序均未啟動 |

失敗：`tests/integration/test_sqlite_store.py:48` 期待 migration `[1..10]`，實際多出 11、12。初始化已執行，但測試不能據此標 PASS。本次未改 assertion、migration 或 production。

跳過：3 個 model real-provider tests（缺 opt-in）、2 個 Groq speech tests（缺 opt-in key）。沒有讀取或將私有 key 放入命令/證據。不能從 skip 推定服務不支援。

## 維持既有行為的驗證基線

| 能力 | 已觀測基線 | 尚未驗證 / future regression condition |
|---|---|---|
| conversation/streaming | integrated test 真 Core/SQLite + fake model 通過 | 真 main + provider + browser delta |
| character | body adapter/mount/failure isolation 通過 | 真 Cubism 畫面/gesture/口型 |
| provider calls | adapter contract 通過 | 真後端及 failover runtime |
| tool calls | 單工具 proposal/auto-approved continuation 合成案例通過 | main argv executor、多工具 batch、執行中 cancel |
| session | turn state machine / persistent repository tests 通過 | UI 多分頁/session、context reload |
| memory/state | memory/identity/relationship/affect tests 通過 | 正式 chat memory ingress；migration test FAIL |
| restart/process recovery | repository reopen/CLI backup tests 通過 | crashed active run reconciliation；不能自動重播副作用 |
| fallback/retry | FailoverModel/job 元件測試通過 | main wiring；output/tool call 後 failover |
| cancellation/timeouts | ConversationEngine/http stream/合成 barge-in tests 通過 | Qwen timeout/cancel、程序樹停止、最新語音正確配對 |
| PC control | scoped driver/Rust isolated tests 通過 | Gateway main executor 的有界記憶體與 readback |
| devices | registry/MQTT/HA simulator或mock tests 通過 | ESP32 真板、真 HA、sensor→actuator |
| Rust | 6 unit tests + Python boundary suite 通過 | Gateway execution 接入、部署程序 supervision |
| config | JSON config tests/CLI 通過 | JSON settings 與 Gateway effective env 一致 |
| shutdown | Gateway callback/hub cleanup test 通過 | Qwen child/active executor cleanup |
| TTS | source 選 Qwen reference v1；先前 session synthesis 為歷史線索 | 本次未重新 GPU 合成或聽測，不標本次 PASS |

未執行完整 scripts/check（含安裝同步、完整 secret scanner）；未跑 24h soak、真雙節點、真硬體、真瀏覽器。Phase 1 不啟動 migration。
