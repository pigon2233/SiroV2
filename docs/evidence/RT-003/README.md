# RT-003 completion — 2026-10-01

Selected task：RT-003 工具 batch 與終止狀態。讀 roadmap 全部 status/dependencies，RT-001/002 DONE，RT-003 是第一張 executable。保留原 dirty tree；本卡沒有開始 RT-004。

## 實作

candidate 的批次 ID 在 dispatch 前固定；先檢查重複 ID、同 session 已用 ID及64-call cap，再循序自動執行。callback只接受terminal proposal，每個call收一次；整批收齊才按原assistant順序附加tool messages、記observation並接續一次模型。model round預算只在batch收齊時遞增，journal cap在candidate按64-call最壞情況計算，不改schema。

candidate run terminal在await前取得唯一claim。取消會fence late callback/delta/result、停止排隊工具並將未開始proposal標denied。已running executor僅抑制late output，不假稱OS process已停止；清理仍RT-005。預設legacy保留。

## Files changed

- src/siro/services/presentation/integrated.py：candidate batch/result/dedup/terminal/queued cancel。
- src/siro/services/tools/orchestrator.py：discard_unstarted，CAS轉pending/approved→denied，不碰running。
- src/siro/services/presentation/gateway.py：拒絕不execute、送terminal callback；approved接受false。
- tests/integration/test_agent_batches.py：7個測試案例，包含100次合成cancel/completion交錯。
- docs/DECISIONS.md、docs/CONTRACTS.md、docs/STATUS.md、roadmap、本證據及source-digests.json。

## Discrepancy / architecture deviations

roadmap未列Gateway檔，但real caller必須修：原ToolApprovalInput只接受Literal[True]，無法拒絕；resolve後仍execute。bool新增接受false，既有true不變；同端點及既有callback，沒有公開協定破壞。D13/contract已記錄。未改provider transports、角色算法、schema、Rust、音色或資料格式。記憶體batch不是durable recovery。

## Tests / results

- 初輪批次+Integrated+Gateway：28 passed。
- 最後相關：`uv run pytest -q tests/integration/test_agent_batches.py tests/integration/test_integrated_companion.py tests/integration/test_gateway.py tests/integration/test_tool_orchestrator.py tests/integration/test_conversation.py tests/integration/test_gateway_main.py`：38 passed，8.33s，exit0。
- 最終 `uv run pytest -q`：206 passed、5 skipped、3 warnings，25.80s，exit0。
- `uv run ruff check src tests`、`uv run mypy`：PASS（165files）；四個受影響source/test format check PASS。
- HTTP denial測試初次422，揭露Literal[True]；修caller後PASS，未吞掉失敗。
- 真provider/speech opt-in五項skip，未宣稱硬體/雲端驗收。Rust未修改未重跑。

## Acceptance

1. 成功+失敗二工具：只執行各一次、兩個paired結果、model只續一次、final一次。
2. 手動拒絕/逆序/重複callback：等待整批、原順序paired、拒絕不execute。
3. 重複call IDs在dispatch前fail，零side effect；step limit產生一次failed terminal。
4. 100次合成完成/取消交錯：final一次，terminal後零assistant_delta/tool_started/tool_result，後續工具不dispatch，DB cancelled。
5. 排隊取消後提案denied、不可重新approve；真HTTP拒絕200且送denied callback。
6. legacy及文字/取消/角色/關係等既有全套回歸通過。

## Remaining issues / rollback

batch/terminal/seen-ID guards僅RAM，重啟recovery屬RT-008；seen-ID沿用DB session+call_id唯一性，provider每次需給新ID，拒絕reuse不自動改ID。長期session guard retention尚無清理策略。已執行OS副作用不會因本卡取消停止（RT-005）。manual HTTP多請求的執行併發仍沿用現有端點；自動批次循序，完整執行handle排程另卡。unknown/unsupported工具與執行backends availability另RT-007。

回滾：drain當前candidate runs，再以SIRO_RUNTIME_PROFILE=legacy處理新runs；不接續candidate中途batch、不重播副作用。需撤回source時只回本卡batch/terminal/discard及HTTP false擴充，保留之前dirty修改。無DB還原需求。
