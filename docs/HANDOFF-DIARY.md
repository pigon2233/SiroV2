# 交接日記（優化補全）

規則：只做本機 commit，NOT PUSHED；不切分支、不開 worktree（owner 2026-11-16 明確允許直接在 main 編輯與本機 commit，
這偏離 AGENTS.md「不直接改 main」）。一次一階段，做完停下等 owner。只 `git add` 自己的檔案。
測試方式：WSL 內 `cd /mnt/e/.../SiroV2 && PYTHONPATH=src:. ~/.venvs/sirov2/bin/python -m pytest -p no:cacheprovider <檔案>`。

## 待辦（依優先）

1. ~~語音可靠度~~ DONE（見下）
2. 每回合分段計時日誌（preface／prefill／first token／TTS queue），之後優化才量得準
3. 提示詞瘦身：system 內 `Registered capabilities` JSON 與 API `tools` 參數重複（AUDIT-2026-10-28 實測 5.9k→4.3k token）；改 prompt 需評測
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
