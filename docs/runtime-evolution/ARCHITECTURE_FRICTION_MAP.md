# Architecture friction map

最小修復都是候選，未授權開始 Phase 2 設計或實作。HIGH 不代表已動態重現所有故障；明列 source inference。

## F01 工具續作失去原生訊息結構

- Severity：HIGH
- Current behavior / Evidence：`integrated.py:continue_after_tool / conversation.py:respond`。
- Root cause：把 observation repr 放進新 user prompt；ModelMessage 無 caller。
- Why it matters：工具語義與原始目標會依 working window 漂移。
- Future impact / Affected subsystem：多步任務與不可信 tool output。
- Smallest possible fix：在既有 ports/core 上接 native messages；先保留 prompt compatibility。
- Risk of leaving unchanged：長任務可靠性不明。
- Risk of changing：provider schema、歷史對話相容。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F02 多工具 batch 逐一遞迴

- Severity：HIGH
- Current behavior / Evidence：`integrated.py:_propose_tool_calls`。
- Root cause：每個 call execute 後立即 continue；inner final 可清掉 run id。
- Why it matters：同批 observations 尚未齊全就繼續模型。
- Future impact / Affected subsystem：multi-call model responses。
- Smallest possible fix：先收齊當批結果再 continuation；用合成兩工具案例確認。
- Risk of leaving unchanged：可能提前 final/後續 call 失聯。
- Risk of changing：批准/錯誤順序行為改變。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F03 取消沒有貫穿執行程序

- Severity：HIGH
- Current behavior / Evidence：`integrated.py:cancel / gateway.py:execute_computer`。
- Root cause：cancel 只到 conversation/body；executor 不接 token。
- Why it matters：使用者停止後 side effect 可能繼續。
- Future impact / Affected subsystem：長程序與 UI 控制。
- Smallest possible fix：把現有取消訊號包進 executor context/handle。
- Risk of leaving unchanged：執行中工作不能可靠停止。
- Risk of changing：誤殺 detach 或已完成 child。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F04 持久 run 不等於可恢復 run

- Severity：HIGH
- Current behavior / Evidence：`services/agent/runs.py / integrated.py:continue_after_tool`。
- Root cause：step counter 在 RAM；latest 不重建 message/tool history。
- Why it matters：crash 後無決定性的下一步。
- Future impact / Affected subsystem：長任務/安裝流程。
- Smallest possible fix：先辨識 interrupted/unknown，再做 observation reconciliation。
- Risk of leaving unchanged：重送風險與遺留 RUNNING。
- Risk of changing：不得自動重播 side effects。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F05 Qwen child/回覆生命周期不完整

- Severity：HIGH
- Current behavior / Evidence：`services/audio/tts.py:QwenReferenceTTS`。
- Root cause：無 close；wait_for timeout 不終止/清空 pipe；無 request id。
- Why it matters：下次 render 可能讀到舊音訊，child 可能滯留。
- Future impact / Affected subsystem：4GB GPU、頻繁取消。
- Smallest possible fix：wrapper 管理 terminate/wait/restart 與 request correlation。
- Risk of leaving unchanged：資源占用/錯配音訊。
- Risk of changing：冷啟動成本/語音回歸。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F06 配置與權限有分立入口

- Severity：HIGH
- Current behavior / Evidence：`gateway.py:main / config.py / runtime rpc`。
- Root cause：Gateway env/direct execution 不經 JSON settings/Rust grants。
- Why it matters：使用者設定與實際限制可能不同。
- Future impact / Affected subsystem：budget/privacy/OS expansion。
- Smallest possible fix：先做 effective-config 與能力/權限對照；保留 full 授權偏好。
- Risk of leaving unchanged：難以驗證設定生效。
- Risk of changing：配置相容與既有操作受影響。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F07 fallback 元件未用於 main

- Severity：MEDIUM
- Current behavior / Evidence：`gateway.py:main / adapters/models/failover.py`。
- Root cause：選單一模型後無 fallback wrapper。
- Why it matters：provider 故障直接終止。
- Future impact / Affected subsystem：local/cloud reliability。
- Smallest possible fix：沿用 wrapper；先訂副作用/串流可重试边界。
- Risk of leaving unchanged：可用性低。
- Risk of changing：重複工具/雲端費用。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F08 memory 沒有完整 ingress/restore

- Severity：MEDIUM
- Current behavior / Evidence：`core/companion.py / core/memory.py`。
- Root cause：recall 有接；working deque 無 restore；chat 無 remember。
- Why it matters：重啟/長聊記不住並非只靠 prompt 能改善。
- Future impact / Affected subsystem：長期人格/關係。
- Smallest possible fix：先驗證事件→候選 memory→commit→recall，不搬 repository。
- Risk of leaving unchanged：體驗斷裂。
- Risk of changing：誤記憶/隱私保存。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F09 瀏覽器狀態每步結束

- Severity：MEDIUM
- Current behavior / Evidence：`gateway.py:browser_tool`。
- Root cause：每 call 建立/關閉 driver，只露 navigate/read。
- Why it matters：driver 的 fill/click 無產品 caller。
- Future impact / Affected subsystem：跨頁任務。
- Smallest possible fix：session wrapper 管理既有 driver。
- Risk of leaving unchanged：複雜 browser task 不可完成。
- Risk of changing：資源釋放、session 隔離。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F10 output 限制發生在讀完之後

- Severity：MEDIUM
- Current behavior / Evidence：`gateway.py:execute_computer`。
- Root cause：communicate 累積 bytes 後才 truncate。
- Why it matters：64KiB 不是峰值記憶體上限。
- Future impact / Affected subsystem：大量 stdout/stderr。
- Smallest possible fix：bounded drain wrapper。
- Risk of leaving unchanged：記憶體壓力。
- Risk of changing：stdout/stderr 排序及錯誤可見性。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F11 基線測試已落後 schema

- Severity：MEDIUM
- Current behavior / Evidence：`tests/integration/test_sqlite_store.py:48`。
- Root cause：期待 1–10，實際 1–12。
- Why it matters：無法宣稱目前全套綠燈。
- Future impact / Affected subsystem：migration/release。
- Smallest possible fix：先核對 migration invariant 再更新正確 expectation。
- Risk of leaving unchanged：回歸訊號被忽略。
- Risk of changing：只改 assertion 會漏真正 schema 回歸。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。

## F12 文件狀態過期

- Severity：LOW
- Current behavior / Evidence：`docs/STATUS.md`。
- Root cause：上方硬體/完成敘述與後方新變更不一致。
- Why it matters：誤導接手者。
- Future impact / Affected subsystem：交接。
- Smallest possible fix：以此次 evidence index 作目前事實入口。
- Risk of leaving unchanged：重複判讀成本。
- Risk of changing：低；預設不進 migration roadmap。
- 驗證層級：F11 本次測試重現；其餘為 source/call-path 查核與待測失敗情境。
