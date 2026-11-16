# 交接日記（優化補全）

規則：只做本機 commit，NOT PUSHED；不切分支、不開 worktree（owner 2026-11-16 明確允許直接在 main 編輯與本機 commit，
這偏離 AGENTS.md「不直接改 main」）。一次一階段，做完停下等 owner。只 `git add` 自己的檔案。
測試方式：WSL 內 `cd /mnt/e/.../SiroV2 && PYTHONPATH=src:. ~/.venvs/sirov2/bin/python -m pytest -p no:cacheprovider <檔案>`。

## 待辦（依優先）

1. ~~語音可靠度~~ DONE（見下）
2. ~~每回合分段計時日誌~~ DONE（見下）
3. ~~提示詞瘦身（能力清單精簡）~~ DONE（見下；真實省多少 token 未量）
4. Ollama `keep_alive` 統一：`hybrid.py` 15m、`numbered.py` 5m、`decision.py` 30m、embeddings／memory_relevance 5m，彼此覆蓋
5. 真正的搜尋來源（目前只有瀏覽器讀頁，DDG CAPTCHA、Bing 讀不到）
6. `docs/collaboration/CONSOLE-REDESIGN-PLAN.md`（記憶自我整理、主線／子線）仍等 owner 審
7. MCP 用戶端（行事曆／信箱之前置）

Owner 已拒絕、不要再提：Rust 移植、UI 選 provider、全螢幕偵測、錄 owner 遊玩、Ollama 500 修補。

## 2026-11-16 階段 1：語音可靠度 — DONE（自動測試層級）

問題（live log 實測）：TTS worker 冷載 117／76／55／57 s（檔案在快取時 17 s）；啟動上限 120 s，
11-16 18:38 預熱逾時後當天沒有再出現 `worker ready`。

修改：
- `src/siro/services/audio/tts.py`：`startup_timeout` 預設改讀 `SIRO_TTS_STARTUP_TIMEOUT`（預設 300 s）；明確傳值者不變。
- `scripts/qwen_tts_worker.py`：新增 `model_hashes()`，把模型檔 SHA256 依（大小、mtime_ns）記在
  `<tts-cache>/model-hashes.memo`，不必每次啟動重算 2.4 GB。指紋值與原本相同，既有語音快取照用。
  （檔名不用 `.json`，因為測試以 `rglob("*.json")` 檢查快取目錄。）

驗證：`tests/test_qwen_worker_completion.py`、`tests/integration/test_qwen_lifecycle.py`、`test_qwen_stream.py`、
`test_worker_idle_unload.py` 共 96 passed；ruff check／format 通過；手動比對有無 memo 的指紋相同、檔案變動後指紋改變。

未驗：真模型冷載實際省多少秒（要重啟 SIRO 後看 log 的 `queue_wait` → `worker ready` 間隔；第一次仍會全算，第二次才省）。
冷載慢的其餘成因（模型載入、CUDA graph 預熱、與 Whisper／Ollama 同時搶資源、WSL 丟 page cache）是推測，沒有分段計時。

未做、需 owner 決定：`SIRO_WORKER_IDLE_SECONDS`（預設 600 s 閒置卸載）調長或設 0 可免去每次重載，
代價是常駐約 2.5 GB RAM 與一塊 VRAM（8 GB 卡上 gemma 已佔 5.65 GB）。

回退：`git revert` 本階段 commit；`model-hashes.memo` 可直接刪。

## 2026-11-16 階段 2：分段計時日誌 — DONE（自動測試層級）

修改：`src/siro/adapters/models/ollama.py` 串流路徑在 done 事件記一行（只有數字，不含內容）：
`ollama timing model=… total= first_text= load= prompt_tokens= prefill= output_tokens= generate=`。
`load`／`prefill`／`generate` 直接取 Ollama 回傳的 `load_duration`／`prompt_eval_duration`／`eval_duration`，缺值記 -1。
TTS 既有 `qwen tts queue_wait`、`worker ready`、`speech synthesized seconds=` 已足夠，未動。

驗證：Ollama contract 三檔 56 passed；ruff check／format、mypy（該檔）通過。
未驗：沒有打真 Ollama 看實際輸出（`tests/real` 的 ollama 測試被 skip）。重啟後 `grep "ollama timing" ~/.local/share/siro/logs/siro.log`。
未做：非串流路徑、Groq／Claude CLI 沒有同樣的計時；Python 前處理時間（AUDIT 量過 <0.1 s）沒有記。

下一步（階段 3 提示詞瘦身）先用這行日誌量一天的 `prompt_tokens`／`prefill` 基準再動 prompt。

## 2026-11-16 階段 3：能力清單精簡 — DONE（自動測試層級，行為影響未評測）

修改：`src/siro/services/tools/orchestrator.py` `ToolCatalogSnapshot.model_context()` 預設輸出精簡版：
去掉 `model_visible`／`display_name`／`version`／`provenance`／`timeout_seconds`、值為 null 的欄位、以及 `reason_code=ready`；
說明文字的「null means unknown」同步改成「a missing field means unknown」。
保留 `available` 與 `output_contract`（即使 null），因為 `test_capability_product.py:161`、`test_capability_inventory.py` 依賴它們。
`SIRO_CAPABILITY_CONTEXT=full` 回到原本輸出。

驗證：`test_capability_inventory.py`、`test_capability_product.py` 14 passed；ruff、mypy（該檔）通過。
合成資料（20 列、metadata 全 null）6,654 → 2,885 bytes。
未驗：live 目錄實際省多少 token（重啟後比對 `ollama timing prompt_tokens`，AUDIT 基準 5,906）；
gemma4:e4b 的工具呼叫行為有沒有變（沒有評測集）。若她開始亂叫或不叫工具，先設 `SIRO_CAPABILITY_CONTEXT=full` 排除。
未做：system prompt 其他段落（人格、記憶、情境）沒動。

