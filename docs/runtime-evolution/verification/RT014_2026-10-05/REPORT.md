# RT-014 Independent Verification — 2026-10-05

Final verdict: **VERIFIED_WITH_MINOR_ISSUES**. 原卡 acceptance 全部 PASS，未發現已確認 regression；minor issue 為新增 memory commit 的取消時序尚無專項動態測試。建議保留 DONE，限 explicit owner statement ingress，不代表完整自然語言抽取、正式部署或 raw history purge。本輪沒有修改 production code、roadmap 或 STATUS。

## 1. Identify target

重新讀取 `RUNTIME_EVOLUTION_ROADMAP.md`：最新 DONE 為 RT-014「有來源的 memory ingress」，完成 2026-10-05；RT-013/015 DEFER。RT-012 是前輪目標，本輪未沿用其結果當作 RT-014 證據。

## 2. Reconstruct intent

閱讀原卡、F08 friction audit、REGRESSION_BASELINE、COMPATIBILITY_PLAN、D30、CONTRACTS、STATUS/SOL_RUNBOOK 與 task evidence。要求如下：

- Objective：明確記憶要求形成有來源的記憶，使用既有 revision 流程。
- Problem / audit：原先只有 recall/API mutation，正式 chat 缺少 remember ingress；working-context restore 已由 RT-010 處理。
- Scope：source event → validated identity/owner memory → durable commit → recall；不推測 facts，不修改 immutable persona、relationship 計算或 retention。
- Acceptance：指定合成事件跨重啟可查，更正/刪除生效且保留來源。
- Compatibility：保留舊 callers、授權、HTTP/WS 與資料；candidate 先接入。
- Tests：remember/correct/delete/restart、tool malicious text、相關 integration、legacy/feature0 對照。
- Rollback：drain、停未來 candidate ingress，保留資料/revision，測試資料走既有 deletion；不自動還原 DB。

實作報告僅作線索。以下結果由本輪 source tracing、實際執行与獨立補查判定。

## 3. Actual code and runtime path

| 檢查 | 判定 / evidence |
|---|---|
| code 存在、不是 detached/stub | `core/memory.py:125` ingest_owner_request 有 explicit prefix parsing、來源/session guard、UUID5、source lookup、既有 remember transaction。實際 main 測試證明有寫入。 |
| caller 及啟用 | `gateway.py` candidate startup 讀取 SIRO_MEMORY_INGRESS_ENABLED，預設1、只接受0/1；IntegratedCompanion startup 建 service，在 candidate user turn 呼叫 ingress。legacy/feature0 tests 無寫入。 |
| 原始來源 | IntegratedCompanion 建立並記錄 siro.presentation UserTextEvent，local_only，含 session/time/text；傳原 event 至 repository，API/SQL source assertions 通過。identity=既有 siro，person=owner；不新增 visitor identity 設計。 |
| output 被 consumer 使用 | durable commit 後將 memory ID/來源及 local-storage 限制放入 verified context；CompanionCore recall 組 prompt。實際 main fresh-session/reopened tests 確認模型取得 remembered/corrected text。 |
| old bypass / hidden fallback | candidate error 轉 FAILED，無 provider dispatch；未暗轉 legacy。工具 continuation 沒呼叫 ingress，真 argv tool output 以 tool role 消費且 browse 為空。 |
| privacy | Core route keyword → MemoryService → SQLite search，cloud requires all memory_sources 明確 cloud_allowed，無來源/unknown/local_only fail closed；actual-main synthetic cloud request 排除本地 memory 與本地 history。 |
| TODO/pass/NotImplemented / duplicate logic | 新必要路徑未見空實作；沒有另建 memory writer/revision store，沿用 existing transaction/correct/delete/FTS；legacy 留舊行为為相容路徑。 |

服務入口依賴 server-created UserTextEvent 和 typed payload，並非任意 tool text 的 public ingestion API。語法限 leading 記住：/請記住：/幫我記住：與 remember:/please remember:，含 ASCII colon；不宣稱 fuzzy extraction 或 fuzzy correction/delete。

## 4. Scope discipline

檢查 completion.patch 全部六 paths：五個 production 檔（memory/core/companion、memory repository、integrated、gateway）和新增 task test。`scope.json` 顯示 current digests 全符合；臨時副本 reverse patch exit0，before hashes 全符合、新 test 消失。沒有回退工作樹；保留原 dirty changes。

repository/Core route privacy filter 与 Gateway flag 超原 tentative file list，但 D30 明確記錄為安全 recall/啟用必要接線。未發現 mass rename/move、無關 refactor、protocol/event format/schema/retention 變更。optional keywords 默认保留旧 callers，未注入 provider/OS/UI internals 到 Core。immutable identity/relationship 演算法沒有 task diff。驗證前後所有 production source hashes 無變，见 final-drift.json。

## 5. Tests / quality

| 本輪 evidence | 結果 | 範圍 |
|---|---|---|
| related.log | 123 passed，無 skip/xfail | memory ingress/v2、persistent/integrated companion、session restore、Gateway/main、batch/journal/terminal fence |
| independent.log / test_independent.py | 1 passed | actual-main 中文 ingress → correction → delete → reopen → fresh model prompt 無原/更正文；revision1–3 source IDs 保存 |
| ruff.log | PASS | src/tests lint |
| mypy.log | PASS，184 source files | type checking |
| scope.json / final-drift.json | PASS | task source boundaries、before/current digests、production 不變 |

合計 **124 passed**；三個依賴 deprecation warnings。初次 verifier 指定不存在 test_memory.py/test_companion_core.py 導致 collection exit4、零測試；保留於 initial-test-selection-error.log，依實際檔名修正後重跑，未算作 production failure 或 PASS。

測試不是只測 mock：actual main/Auth/ASGI/Core/SQLite/來源/FTS/revisions 為 production path；tool injection 使用真 argv subprocess。模型與 body 為合成 fixture，未外呼 paid provider。寫入失敗透過 monkeypatched remember 模擬，確認 FAILED、零 model dispatch/記憶；空命令亦不造 fact。plain prose/quotes、來源拒絕、identity、idempotency、cloud/local route、legacy/off 均覆蓋。

本輪未跑 full suite；報告中的426 passed/5 opt-in skipped是 implementation 歷史結果，不计入本輪。未做 flaky 長測。專項未測 memory commit await 的 cancellation-before/during/after race；相鄰 terminal/cancel tests 不等於該新增 await 的完整時序證據。

## 6. Relevant regression baseline

| 能力（限定本卡路徑） | 判定 | Evidence / 限制 |
|---|---|---|
| memory/state | PASS | 原 memory v2 與 ingress tests，source/revision、correct/delete、identity；未宣稱完整 chat intelligence |
| restart/process recovery | PASS | SQLite reopen、main lifecycle 重建、fresh-session recall/刪除後排除；非 abrupt OS power-loss durability 測試 |
| session/context | PASS | session restore / integrated tests；本地記憶可跨 session recall，cloud route 排除 local-only |
| conversation/streaming | PASS | 真 Core/SQLite + synthetic model 相鄰與 main tests；真 provider/GUI 未驗 |
| tool calls | PASS | 真 argv observation 不自動 ingest；batch/journal/fence 相鄰回歸 |
| config / compatibility | PASS | legacy/feature0 停 ingress、舊 HTTP/API tests；不代表全域 settings/env 一致性 |
| cancellation — existing adjacent fence | PASS | terminal-fence/journal/integrated 相關 suite；仅既有測試層級 |
| cancellation — new memory commit race | NOT VERIFIED | 只有 source 中 commit 前後 terminated checks，沒有專項時序 fixture |
| 真 provider、owner GUI、24h soak、power loss、部署 rollback | NOT VERIFIED | 沒有本輪執行證據 |

沒有已確認 FAIL baseline；無關的 device/audio/browser/Rust 不重驗。不得用本表 PASS 推論那些 subsystem 正常。

## 7. Acceptance criteria

將原卡合併句拆為三項，逐項判斷：

| Criterion | 判定 | Evidence |
|---|---|---|
| 指定合成事件跨重啟可查 | PASS | test_actual_main_remember_correct_delete_restart_provenance：實際 main 寫入、重建 lifecycle，memory ID 持續可查，fresh session model prompt 消費記憶。 |
| 更正/刪除生效 | PASS | 真既有 HTTP correct/delete、revision2/3；更正後 fresh prompt 有新文；獨立測試 delete→reopen→fresh prompt 原文和更正文皆不存在。 |
| 保留來源 | PASS | 原 event envelope text/session/source SQL assertions、memory_sources；獨立補查 revision1 原 source、revision2 原+correct source、revision3 保留來源。 |

反推測要求亦 PASS：prose/quote 不寫入，非 presentation source 拒絕，真 tool observation 不寫入。刪除使 active memory recall 失效，未 purge 原 conversation history；這是既有 retention，不是本卡 regression。

## 8. Final verdict

**VERIFIED_WITH_MINOR_ISSUES**

- Evidence：124 tests passed、actual-main/Core/SQLite/HTTP/model-consumer、真 tool subprocess、獨立 deletion/revision probe、ruff/mypy、scope/digest。
- Issues found：專項缺 memory commit cancellation race 測試；無已確認 runtime failure 或 regression。
- Severity：LOW（verification coverage gap；不是已證實取消後誤寫）。
- Required fixes：本卡 acceptance 無必修 production fix。若宣稱 commit 取消時序已完整驗證，需先補專項動態證據或縮小該宣稱。
- Optional improvements：加入取消前、寫入阻塞中、commit 已完成後的 deterministic fixtures，驗證 provider/late-output fence、durable transaction 結果；另做獨立 OS-process crash/restart 和部署 drained rollback。
- Roadmap DONE：**保留**。原卡三個 acceptance 已有實際證據；不建議降為 PARTIAL/BLOCKED/FAILED_VERIFICATION。真服務/部署及取消時序缺口繼續標 NOT VERIFIED。

所有本輪資料與對話均為 synthetic/temp fixture；production 未修改，未碰私人 DB 或部署。
