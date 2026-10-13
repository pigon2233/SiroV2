# RT-004 completion — 2026-10-01

Selected：RT-004，roadmap最前未完成且dependency RT-001 DONE。RT-005/006等未開始。現有dirty修改保留。

## Runtime path / changes

Gateway main → ToolOrchestrator computer.execute closure → 原argv/cwd/timeout/detach/privileged/shell/env檢查 → candidate execute_bounded_argv facade。legacy保持原communicate/read後截斷分支。新facade並行讀stdout/stderr，共用64KiB raw retention budget，超出繼續drain/discard，保留returncode/stdout/stderr/truncated等欄位。

Files：src/siro/services/tools/execution.py（新增）；src/siro/services/presentation/gateway.py（candidate binding）；tests/integration/test_bounded_execution.py；docs/DECISIONS.md、CONTRACTS.md、STATUS.md、runtime roadmap；本目錄evidence/measurement/script/digests。

Timeout會kill/reap直接child，取消reader後恢復drain，避免pipe滿時wait死鎖；cleanup最多5秒。沒有實作run token/process group lifecycle（RT-005）。detach保持舊started/pid/argv觀測。

## Tests

- 最終相關：bounded_execution、gateway_main、gateway、agent_batches、integrated_companion、computer_driver：41 passed，10.00s。
- 全套 `uv run pytest -q`：213 passed、5 skipped、3 warnings，28.21s，exit0。
- `uv run ruff check src tests` PASS；`uv run mypy` PASS（167files）；三個受影響source/test format check PASS。
- main組裝測試只替換provider/uvicorn server；實際main、HTTP callback、Core/SQLite、ToolOrchestrator、argv subprocess都執行，legacy/candidate結果均符合。不是只測未註冊helper。
- 100MiB stdout/stderr洪流、邊界精確6bytes、exit7、detach、靜默與無限輸出timeout均測過。
- 5個真provider/speech opt-in skip，不宣稱真雲端/GPU/硬體驗收；Rust未修改未重跑。

## Measurement / acceptance

`uv run python docs/evidence/RT-004/measure.py` 可重跑；測試資料合成，無私人檔案/密鑰。
measurement.json：輸出104857600 bytes，保留65536 bytes，truncated=true，returncode0；parent RSS baseline25513984、peak25923584、delta409600 bytes（400KiB），1ms採樣73次，elapsed約0.088s。

達到cap≤64KiB與額外RSS<32MiB，兩pipe無deadlock。RSS只量executor parent，不含child，且採樣不是連續追蹤；此數值只屬本機Python3.14.4合成fixture，不推論所有程序/RSS峰值。

## Discrepancy / deviations / limitations

原closure是各管道64KiB（合計可能128KiB），roadmap要求cap≤64KiB。本卡candidate採共享64KiB；超限時兩管道保留份額依讀取時序，既有欄位/小輸出行為相容。D14記錄此差異，legacy不變。raw bytes解碼遇不合法UTF-8時replacement字符可能增加重新編碼後長度；64KiB是raw retention cap。

無Rust RPC、授權defaults、browser、schema/config格式或角色變更。helper非新的授權入口：只有Gateway既有驗證後才呼叫，未提供新的公開endpoint。權限與process tree取消完整整合另卡。

Rollback：排空candidate當前工作後，新runs用SIRO_RUNTIME_PROFILE=legacy（原executor binding）。撤回本卡gateway分支/helper不影響DB，保留其他dirty修改；不接續中途job、不重播副作用。
