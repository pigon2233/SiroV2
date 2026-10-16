# RT-012 independent verification — 2026-10-05

Final verdict: **VERIFIED**. 建議保留 roadmap 的 DONE，限於本卡定義的 ephemeral、同 session browser workflow；不延伸為登入、跨重啟 browser 恢復或正式部署驗收。本輪沒有修改 production code、roadmap 或 STATUS。

## 1. Target selection

讀取 `RUNTIME_EVOLUTION_ROADMAP.md`，最近完成的 DONE 為 RT-012「持續 browser session」（2026-10-05）。RT-013/015 DEFER，RT-014 BLOCKED；未要求 owner 指定。RT-014 的歷史依賴文字仍指已完成的 RT-010，與本卡驗收無關。

## 2. Reconstructed intent

依據 roadmap 原卡、F09 audit、CAPABILITY_MATRIX、COMPATIBILITY_PLAN、REGRESSION_BASELINE、D29/CONTRACTS 與 implementation evidence 重建要求，未將 implementation report 的 PASS 當作獨立證據。

- Objective：同 session navigate/read/fill/click，操作後有 readback，且能清理。
- Problem / audit：既有 scoped driver 每次 navigate 都重建，無法持續跨步操作。
- Scope：browser ownership wrapper、Gateway composition、candidate tool catalog；禁止擴張 OS desktop 或保存登入憑證。不修改 driver 核心。
- Acceptance：跨步狀態保留、操作後 readback、過期目標拒絕。
- Compatibility：保留舊 callers、授權與 HTTP/WS 契約、資料；新行為先 candidate。
- Tests：本機跨頁表單、A/B 隔離、stale target、cancel/close，並回歸相關 integration 與 legacy/off profile。
- Rollback：停止新 jobs，清理 owned browser，再於 drained startup 關閉 `SIRO_BROWSER_SESSION_ENABLED`，回 stateless navigate；不降版 DB。

## 3. Actual code / runtime path

| 檢查 | 判定及 evidence |
|---|---|
| Code 存在、非 detached/stub | `services/tools/browser_session.py` 有 session lock、driver ownership、origin/epoch、TTL、bounded actions、清理；真 Chromium 跨頁表單測試執行該實作。 |
| Runtime caller | `gateway.py:1143` 建 pool；`:1352` contextual executor 呼叫 `execute`；`:1389` descriptor / `:1402` orchestrator binding；`:1425` startup，`:1475` shutdown。實際 main/Core/SQLite/catalog 測試通過。 |
| Config 啟用 | candidate 預設 flag=1；僅接受 0/1。legacy 或 flag=0 保留 stateless，對照 fixtures 通過。 |
| Hidden fallback / 舊路繞過 | candidate arguments-only handler 明確 PermissionError，不偷偷改走 stateless。舊 handler 僅供 legacy/off；readiness/catalog/kill-switch 仍受既有 gates 控制。 |
| TODO/pass/NotImplemented | 新 session runtime 未發現代替必要行為的空實作；Gateway 既有 protocol declarations/default callbacks 不被當成本卡實作。 |
| Duplicated logic | session wrapper 使用既有 ScopedBrowserDriver 及 BrowserTarget，未複製 DOM locator/screen hash 邏輯；保留 stateless 是相容路徑。 |
| Output consumer | 實際 main 測試的 synthetic model 取得工具 readback，讀到 Saved Runtime；結果經 orchestrator continuation / journal 配對。不是只測 wrapper return value。 |
| Stale fence | epoch 前綴隔離 session / recreated driver，既有 DOM hash 驗證操作目標；DOM 改動、跨 session、TTL、origin reset 均有測試。 |
| Error / cleanup | token、task、repeated cancellation、deadline、active close/shutdown 會清理；無法完成 cleanup 時報 ExecutionCleanupError 並封閉 pool，不默默成功。 |

持續狀態限同 origin、同 Gateway process；切 origin 重建 scope，任意 operation error 關閉受影響 session。WebSocket disconnect 沒有 conversation-owner mapping，由 idle TTL 清理，為已記錄限制。

## 4. Scope discipline

`scope.json` 對 task completion patch 的五個 source/test 檔案驗證 current digest；在臨時副本 reverse patch 成功，三個既有檔案符合 before digest、兩個新增檔案消失。沒有在工作樹執行回退。

新增 service wrapper 取代原預期 adapter wrapper，D29 有理由與範圍記錄；driver 核心未變。Gateway optional shutdown callback、candidate schemas 與 enum validation 是必要接線。未見 mass rename/move、無關 subsystem refactor、HTTP/WS protocol 或 DB/state format 變更。新增 dependency 由 composition root 綁定，Core 不持有 Playwright internals。production digest 前後比對見 `final-drift.json`。

## 5. Tests independently rerun

| Evidence | 本輪結果 | 測試層級 |
|---|---|---|
| `related.log` | 154 passed；無 skip/xfail | browser sessions/catalog、execution lifecycle、Gateway/main、orchestrator/batches/journal、terminal fence/session restore |
| `driver.log` | 1 passed | 真 headless Chromium、既有 scoped driver |
| `independent.log` / `test_independent.py` | 1 passed | 獨立 actual-main HTTP workflow：A/B 真 browser，HTTP cancel 已完成 A turn 後回收 A，B 仍存活；shutdown 再回收 B |
| `ruff.log` | PASS | lint |
| `mypy.log` | PASS，183 files | type checking |

共 **156 passed**。三種 dependency deprecation warnings，不是 skip/xfail 或本卡 runtime failure。未重跑 full suite；implementation report 的 419 passed / 5 opt-in skipped 是歷史結果，不計入本輪。

測試品質：跨頁 fill→next→save、跨 run state、stale、隔離與 TTL 使用真 Chromium、本機 HTTP 表單。main 測試使用真 Core、SQLite、ASGI、catalog/contextual executors，但模型是合成 fixture。timeout/repeated cancellation/cleanup failure 使用可控制的 fake driver，能覆蓋錯誤時序但不是 Chromium hang 的實測。legacy/feature0 對照驗證兩 calls 兩 drivers 回收。收集及執行的相關 tests 沒有 skip/xfail；未聲稱所有 repository tests 都已執行，亦未做長期 flaky/soak 判定。

## 6. Relevant regression baseline

| Baseline 能力 | 判定 | Evidence / 限制 |
|---|---|---|
| tool calls | PASS | catalog、batch、配對 continuation/journal、kill-switch 與 main browser 路徑相關測試 |
| PC control — browser slice | PASS | 真 Chromium scoped driver、持續操作與 readback；不涵蓋 OS desktop |
| session | PASS | A/B 隔離、跨 run state、session restore tests；不代表 owner GUI 多分頁驗收 |
| cancellation/timeouts | PASS | task/token/repeated cancel/deadline/cleanup failure fixtures，加獨立真 browser HTTP cancel；不涵蓋 TTS/程序樹 |
| shutdown | PASS | active cleanup tests、main lifespan 與独立 A/B browser 回收 |
| config / compatibility | PASS | candidate default、feature0/legacy stateless catalog/executor、原 HTTP/WS tests；不代表 settings/env 全域一致性 |
| restart/process recovery — adjacent guard | PASS | run journal/session restore/terminal fence 相關測試；沒有新增 browser replay/state migration |
| 真 provider + owner GUI、browser 跨 process state 恢復、24h soak、部署 rollback | NOT VERIFIED | 不在本卡已完成能力的證據內；browser state 明確 ephemeral，rollback 僅 fixture / source reverse dry check |

此處 PASS 僅代表欄內限定路徑。沒有發現本卡造成的 regression；無 FAIL baseline。其他不相關 subsystem 未重驗。

## 7. Acceptance criteria

| 原卡 criterion | 判定 | Evidence |
|---|---|---|
| 跨步狀態保留 | PASS | `test_real_chrome_cross_run_form_isolation_stale_ttl_close`，真 Chromium fill→next→save、跨 run 保留值；`test_main_catalog_real_browser_across_runs_and_shutdown` 證明實際 caller 使用同 pool。 |
| 操作後 readback | PASS | wrapper navigate/read/fill/click 回傳 url/title/text/screen_version；main test 的 model continuation 取得 Saved Runtime，經真 orchestrator/journal 路徑。 |
| 過期目標拒絕 | PASS | stale-after-fill、跨 session、close/recreate epoch、TTL 與 origin reset tests；使用既有 driver DOM fence，非只檢查 synthetic return。 |

## 8. Verdict / disposition

**VERIFIED**

- Evidence：156 個本輪 passing tests、真本機 Chromium、actual-main HTTP cancel 獨立測試、production call chain、current/before digest / reverse dry check、ruff/mypy。
- Issues found：未發現可證實的 acceptance failure、scope violation 或 regression。
- Severity：無已確認缺陷。
- Required fixes：無。
- Optional improvements：將獨立 HTTP idle-session cancel 案例納入正式 suite；後續做長期 browser cleanup soak 與實際部署 drained rollback 演練。
- Roadmap DONE：**保留**。不需要改為 PARTIAL/BLOCKED/FAILED_VERIFICATION。已知 ephemeral/cross-origin/WS TTL 限制應繼續保留於卡片，避免擴張完成宣稱。

所有動態測試使用本機合成表單、臨時資料與合成 model；未用私人 DB 或 paid provider。驗證 artifacts 位於本目錄，production code 未修改。
