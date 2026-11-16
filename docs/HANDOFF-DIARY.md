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


## 2026-11-16 VRAM 實測（owner 目標：SIRO 總佔用 < 4 GB）— 只有量測，未改程式

量法：Windows `Get-Counter '\GPU Process Memory(*)\Dedicated Usage'` 的 `vmwp`（= 整個 WSL）；TTS 另用 `nvidia-smi` 差值。
Windows 自己（dwm、Discord 等）另佔約 1.0 GB，不算 SIRO。RTX 3050 8 GB，gemma4:e4b 是 7.5B Q4_K_M、含視覺／聲音 projector 與 draft 模型。

| gemma4:e4b 設定（ctx 8192） | WSL VRAM | 生成速度 |
|---|---|---|
| 預設（全部上 GPU） | 4,645 MB | 53 tok/s |
| `num_gpu=42` | 3,367 MB | 45 tok/s（5.7k token prefill 3.7 s，1,545 tok/s） |
| `num_gpu=40` | 3,245 MB | 40 tok/s |
| `num_gpu=36` | 2,997 MB | 31 tok/s（prefill 4.5 s） |
| `num_gpu=30` | 2,629 MB | 25 tok/s |
| `num_gpu=24` | 2,267 MB | 19 tok/s |
| `num_gpu=12` | 1,599 MB | 11 tok/s |
| `num_gpu=0` | ≈0 | 10 tok/s |
| ctx 4096（全 GPU） | 4,583 MB | 只省 60 MB，不值得 |
| `draft_num_predict=0`（全 GPU） | 4,499 MB | 45 tok/s，變慢又沒省多少 |

Qwen3-TTS worker（cuda-graph、bf16）：載入後 torch allocated 2,070 MB，warmup 後 2,332 MB，整個行程約 2.7 GB。
talker 就佔 1,728 MB 且已是 bfloat16，沒有 fp32 可省。**檔案在 page cache 時 worker 8 秒就 ready**，
所以 55–117 秒的冷載主要是從磁碟讀 2.4 GB（WSL 丟掉 page cache），不是運算。

結論：兩個模型同時常駐最少也要 1.6 + 2.7 = 4.3 GB（而且那時 gemma 只剩 11 tok/s），同時常駐 < 4 GB 做不到。
可行路線：(A) `num_gpu=42` + TTS 閒置卸載＝平常 3.4 GB、說話時短暫 6.1 GB；(B) 嚴格分時，兩者不同時在顯卡，峰值 3.4 GB，
每次說話前多等約 8 秒；(C) 對話走 Groq、TTS 常駐＝2.7 GB；(D) gemma `num_gpu=42` 常駐、語音改 Edge／Kokoro＝3.4 GB、聲線會變。
`OllamaAdapter` 目前沒有 `num_gpu` 選項（電腦操控有 `SIRO_COMPUTER_OLLAMA_GPU_LAYERS`）；`launch_companion.py` 只從 `.env.local` 讀白名單內的鍵。
