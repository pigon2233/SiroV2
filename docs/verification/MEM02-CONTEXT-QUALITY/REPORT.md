# MEM02 理解品質：候選拒收與新案例

2026-10-22 Asia/Taipei，FAILED_VERIFICATION / CANDIDATE_REVERTED / LOCAL_ONLY。
Base f85c7115fd03dabe00f63f9469add8966c69338e，branch codex/memory-context-quality-20261022。
本輪確實測真模型，沒有改善品質的合格production變更；交付凍結新題、capture回歸與失敗證據。

## 同模型量測

沿現有Ollama qwen3:4b-instruct，digest
0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0。
本機API／模型前後核對，既有temperature0.7／top_k20／top_p0.8／repeat_penalty1、
無seed；沿原adapter think=false、2048輸出預算、45秒provider timeout，未換模型或下載。
WSL剛啟動時tags首次超時，待既有服務ready後可讀，未重啟／修改服務或誤報未安裝模型。
用既有WSL ext4 venv；未讀私人DB／key／對話，全部輸入與SQLite均合成。

| 批次 | capture | 原自動分數 | 加正文審閱的同題分數 | 判定 |
| --- | --- | --- | --- | --- |
| baseline | 30/30 | 22/30 | 21/30 | C19角色錯置硬失敗，未達27 |
| 唯一候選 | 30/30 | 20/30 | 19/30 | C03工具完成錯標、C04/05角色錯置，拒收 |

兩批是各一次，不抽樣挑好分數。來源UUID／時間與非固定採樣都有變動，不能把分數差異
全歸因於候選，亦不當統計顯著下降。舊25/30歷史保留，不能當成目前保證。
正文由Codex讀全部60份回答並對照固定fixture，非真人或獨立第二模型。
每題六項檢查與理由在兩份review；既有response-bound工具兩批均exit1。
自動分數／原題／rubric／27門檻／body hard gates都未調整。

候選只將既有context policy整理為繁中核對步驟、移到system結尾，並把affect coping
說明改為有來源狀態才適用。C19本批改對『你喜歡』、C22少問問題，但C03卻把記憶更正
標成verified_tool_completion=true，C04/05在無有效偏好時說自己的飲品喜好，整體不合格。
原typed source JSON、native history、snapshot／preflight與權限程式沒有修改。
拒收後保存rejected-candidate.patch，僅將自己兩個production檔還原至本基線；
git diff --exit-code HEAD -- src 通過。git apply --check該patch通過，未再次套用或部署。

## 容量診斷的範圍

撤回後額外兩次非串流request只量原提示的provider終止與用量，不計入批次分數：
C19 prompt_eval_count1764／eval_count33，C21為2261／78；均done=true／stop。
當時模型ps的context_length4096，API payload7484／8626 bytes。
這兩題沒有輸入達容量上限的跡象，不能推斷其餘題／長對話永遠不截斷，
也不能把兩次量測當成本或延遲SLO。非串流與原串流路徑不同，僅作診斷。
C19仍第一人稱錯置，C21這次卻指出衝突，說明同版有波動；不拿這題重抽替換原失敗。
模板／參數只讀核對，無已證實模板故障；未修改全局num_ctx或採樣設定。

## 新題與L1回歸

在候選結果出來之前凍結12題context_quality_holdout.json：新活動／鍵盤配置／
資料夾歧義／溫度回報／病毒掃描計畫／上傳停止／取消目標／小說引用／
偏好更正／guest scope／unknown與completed readback。
原始bytes SHA256 11d0d021f92137919d08d3bdcc193fc35dc858667e79c47d874b5209e238abd9。
fixture由本對話作者建立，不稱獨立盲測或真人資料。
候選在原題已硬失敗，因此不擴大真模型測試；這12題只驗actual Core／SQLite capture，
結果不計成理解。新增12項參數測試檢查原native request、來源必要／禁止片段與privacy等。

最終215 passed / 0 failed / 0 errors / 0 skipped，pytest26.54s，harness30.447s；
2既有warnings（Starlette httpx棄用提示、adapter finally-return），未抑制。
source_before == source_after，content SHA256
5738e7ab3ad99a3bdc6a99b293ea2bb1d0990fd91a06a34aaf30d83b1fa74bea。
修改的測試Ruff lint／format、mypy與git diff --check通過。
測後只增補報告／證據，未更改Python。未重跑前卡1263或整套scripts/check，不宣稱main已驗。

## 重現與接續

命令在本工作區WSL，Python從workspace .venv/bin/python啟動：

```text
env -u SIRO_OPENAI_BASE_URL -u SIRO_OPENAI_MODEL -u SIRO_OPENAI_API_KEY SIRO_OLLAMA_MODEL=qwen3:4b-instruct SIRO_OLLAMA_BASE_URL=http://127.0.0.1:11434 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python scripts/evaluate_context_understanding.py --mode real --git-executable git.exe --output <新json>
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python scripts/run_acceptance.py <final-receipt.json全部targets> --output <工作區外新目錄> --level L1 --git-executable git.exe
.venv/bin/ruff check tests/integration/test_context_understanding.py
.venv/bin/ruff format --check tests/integration/test_context_understanding.py
.venv/bin/mypy tests/integration/test_context_understanding.py --cache-dir /tmp/siro-quality-mypy-20261022
```

candidate當時source hashes在candidate-real.json；patch僅供隔離研究重現，勿在產品套用。
精確審閱輸入的evaluation／review／fixture bytes保存在review-inputs.base64.json，防Git換行
導致歷史hash失配。解碼至新的工作區外目錄後，用既有腳本--mode review，分別指定
--evaluation <baseline或candidate-evaluation.json>、--review <對應review.json>、
--evaluation-fixture <fixture.json>、--output <新結果>。預期兩批都exit1，21/30與19/30。
base64皆為合成測試資料，無secret；讀入bundle後用標準庫base64.b64decode(value,validate=True)
逐檔write_bytes即可。原raw logs／診斷腳本留E:/coding/Worktrees/memory-context-quality/。
本輪已實際解碼到reproduce-review-v1並重跑兩份審閱，exit1與21／19分均吻合。

下一步先固定可重現的語義對照條件，分開採樣波動、來源序列化與模型能力問題，
再決定可驗的最小修復；不繼續無界prompt嘗試，也不直接替換／下載較大模型。
MEM02、正式聊天接線、審閱清除、背景保存、提醒與T30 trace feed仍未完成。
共享STATUS／DECISIONS／CONTRACTS依既有owner分工交整合者更新。
未改私人服務、資料或模型設定，未push／PR／合併／部署，未做人機／真工具／硬體／長時間驗收。
