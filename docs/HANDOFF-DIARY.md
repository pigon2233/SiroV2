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

## 2026-11-16 方案 A 第一步：對話模型可設定顯卡層數 — DONE（自動測試層級；預設不變）

Owner 的限制（2026-11-16）：聲音與對話品質都不能降，SIRO 總 VRAM 目標 < 4 GB。所以不換聲線、不換小模型。

修改：
- `src/siro/adapters/models/ollama.py`：讀 `SIRO_OLLAMA_GPU_LAYERS`（0–256 整數），有設才在 `options` 加 `num_gpu`；沒設＝行為不變。
- `scripts/launch_companion.py`：`.env.local` 白名單加 `SIRO_OLLAMA_GPU_LAYERS`、`SIRO_OLLAMA_KEEP_ALIVE`（後者原本讀不到）。
- 新增 `tests/contract/test_ollama_gpu_layers.py`。

驗證：Ollama contract 四檔＋`test_companion_launcher.py`＋`tests/unit/test_model_router.py` 80 passed；ruff、mypy（adapter）通過。

要生效：owner 在 `.env.local` 加 `SIRO_OLLAMA_GPU_LAYERS=42` 後重啟（我沒有改 owner 的 `.env.local`）。
未驗：設了之後 live 對話的實際 VRAM 與速度（上表是直接打 Ollama API 量的）。
已知風險：其他直接打 Ollama 的呼叫點沒有帶 `num_gpu`（`ollama_memory_relevance.py`、電腦操控的 `hybrid.py`／`numbered.py`／`decision.py`，
後者有自己的 `SIRO_COMPUTER_OLLAMA_GPU_LAYERS`）。若它們用同一個模型但選項不同，Ollama 可能重載回全 GPU；要看 `journalctl --user -u ollama` 的載入次數確認。

下一步（方案 A 第二步）：讓 TTS 模型檔留在 page cache，使閒置卸載後重載約 8 秒而不是 55–117 秒。
候選做法：Windows 使用者目錄 `.wslconfig` 的 `[experimental] autoMemoryReclaim=disabled`（改 owner 的系統設定，需 owner 同意），
或 gateway 定期讀一次模型檔。兩者都還沒做、也還沒驗證哪個有效。

## 2026-11-16 方案 B（owner 選定）：兩個模型輪流用顯卡 — 只有量測，未改程式

Owner：選 B，但「8 秒有點過分」，希望模型在不同記憶體間搬移。實測（拋棄式行程，`faster_qwen3_tts`，cuda-graph）：

| 動作 | 時間 |
|---|---|
| TTS 模型 `root.to("cpu")`（`root = fast.model.model`）＋丟掉兩個 graph＋`empty_cache` | 1.0–1.2 s |
| `root.to("cuda")` | 0.3 s |
| 重建 `PredictorGraph`／`TalkerGraph`＋`warmup(prefill_len=100)` | 1.0 s |
| gemma4:e4b 由 Ollama 重載（檔案在 page cache） | 4–5 s，另加整段提示詞重新 prefill（5.7k token 約 3.7 s） |

重點：
- 搬回 GPU 後**不重建 graph 就生成會 `CUDA error: device-side assert`**，而且會弄壞整個 CUDA context；一定要重建再 warmup。
  重建方式照 `faster_qwen3_tts/model.py` `from_pretrained` 後半（`talker = root.talker`、`cfg = root.config.talker_config`、
  `pred = talker.code_predictor`，`PredictorGraph(pred, pred.model.config, cfg.hidden_size, device, dtype, do_sample=True, top_k=50, temperature=0.9)`、
  `TalkerGraph(talker.model, cfg, device, dtype, max_seq_len)`，再把 `_warmed_up=False` 後 `warmup`）。
- 停在 RAM 時 torch 仍 allocated 約 390 MB（speech tokenizer、voice prompt 沒跟著搬）加上 CUDA context，
  估計還佔 0.7–0.9 GB VRAM。要讓 gemma(42 層 3.4 GB)＋停放的 TTS < 4 GB，得連 speech tokenizer 一起搬，或把 gemma 降到 36 層（3.0 GB、31 tok/s）。未驗證。
- 冷啟時 `import torch` 14.7 s、`from_pretrained` 50.9 s（page cache 幾分鐘內就被丟掉）；常駐 worker 把權重留在自己的 RAM 可以完全避開。
- 這輪測到的生成時間（20 s）不可信：參考文字是假的，而且背景自主活動中途把 gemma 載回 GPU 搶資源。

實作分段（都還沒做）：
- B1 worker：`qwen_tts_worker.py` 加 `{"park": true}`／`{"unpark": true}` 指令（搬移＋重建 graph），`QwenReferenceTTS` 閒置時改成 park 而不是殺行程。
- B2 gateway：合成前先讓 Ollama 釋放（`keep_alive: 0` 的空請求），合成完再預載 gemma；回覆要整段生成完才開始合成（現在第一句會邊生成邊合成，兩者會同時在 GPU）。
- B3 背景工作（自主活動、記憶整理、電腦操控）在說話期間不得把 gemma 叫回來，否則會超過 4 GB。
- 預期體感（推估，未跑過整個流程）：文字生成完到開始出聲多約 1.5 s；說完話後 gemma 在播放期間重載，緊接著的下一句可能多等數秒。

## 2026-11-16 繞過 Ollama 直接跑 llama.cpp — 實測後**不建議現在換**（未改程式）

Owner 要求直接換。先實測，結果不支持：

- Ollama 0.34.3 本來就是啟動內建的 `~/.local/ollama/0.34.3/lib/ollama/llama-server`。它的完整指令（`ps` 抓到）：
  `--model <blob 370c28…> -c 8192 -np 1 --no-jinja --chat-template chatml --mmproj <blob 4cb21b…> --no-mmproj-offload --spec-type draft-mtp --spec-draft-n-max 3
  --spec-draft-backend-sampling --spec-draft-model <blob 05612e…> --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on -b 512 -ub 512 -ngl 42 --context-shift --keep 4`。
  `--no-jinja --chat-template chatml` 表示提示詞樣板與工具呼叫的格式化／解析是 Ollama 的 Go 層在做，不是 llama.cpp。
- 我用同一個執行檔在 38999 埠直接啟動（改 `--jinja`、不帶 mmproj）：啟動 3.2–3.4 s，和 Ollama 自己記錄的 3.77 s 差不多，**載入時間沒有賺到**。
- 我設的 `LD_LIBRARY_PATH=$L:$L/cuda_v13` **沒有載到 CUDA 後端**（GPU 只多約 200 MB，5.7k token prefill 83 s、生成 13 tok/s＝在跑 CPU）。
  Ollama 另外給了什麼環境變數才載到 GPU 後端，沒查出來。所以直接跑的 GPU 載入秒數其實沒量到。
- `--slot-save-path` 的 save／restore 本身很快（5,808 token，62 MB，0.03 s／0.02 s），但重啟後 restore 再送「相同前綴＋新一輪」，
  `cache_n=0`、整段重新 prefill。也就是「存回對話狀態省掉重讀提示詞」**沒有照預期生效**，原因未查。
- `--jinja` 下 `/v1/chat/completions` 的工具呼叫可用（回了正確的 `tool_calls`），但一般對話 60 token 的 `content` 是空的（可能全進了思考區），
  行為和 Ollama 的樣板不同，換過去需要重新評測對話與工具品質。

結論：先前「直接跑可降到 2–3 秒且免重讀提示詞」是推估，實測沒有證據支持。換掉 Ollama 要自己處理樣板、工具解析、GPU 後端載入與行程管理，
風險高而好處未證實。gemma 回到顯卡仍以「Ollama 重載約 4 s＋重新 prefill」估算。若之後要再試：先查 Ollama 啟動 runner 時的環境變數，
並用 `--no-jinja --chat-template chatml` 加上 Ollama 產生的原始提示詞來比對 slot restore。

## 2026-11-16 方案 B 第一段（B1 worker 端）：TTS worker 支援 park／unpark — DONE（真模型實測；用戶端尚未使用）

修改：`scripts/qwen_tts_worker.py`
- `FastVoiceClone.park()`：丟掉兩個 CUDA graph、`model.model.to("cpu")`、`empty_cache`。`unpark()`：搬回 GPU、照 `from_pretrained` 重建兩個 graph、`warmup`。
- stdin 指令 `{"park": true}`／`{"unpark": true}`，回 `{"parked": bool, "seconds": float}`（帶回 `request_id`／`epoch`）。
- 合成／串流請求遇到 parked 會先自動 `unpark`；快取命中不需要 GPU，parked 狀態下照樣回。
- **`QwenReferenceTTS`（`tts.py`）還沒送這兩個指令**，所以目前行為完全不變。

驗證：worker 相關四個測試檔 96 passed；ruff 通過。真模型＋真聲線、暫存快取目錄，直接驅動 worker：

| 動作 | 時間 |
|---|---|
| park | 0.85–0.99 s |
| unpark（含重建 graph） | 1.40 s |
| unpark 後第一句合成 | 4.2–5.8 s（暖的時候同長度 1.1–1.3 s） |
| parked 時快取命中 | 0.00 s |

誠實的結論（比先前推估差）：
- 「回到顯卡約 1.3–1.5 秒」只是搬移＋重建；**第一句合成還會多慢 3–4 秒**（graph 首次重播），所以從 parked 到出聲實際約 5–6 秒，不是 1.5 秒。
  當時 gemma 也在 GPU 上（總用量 7.8／8 GB），有搶資源的成分，獨佔時是否較快沒量。
- park 只讓 `nvidia-smi` 少約 0.7 GB（7,785 → 7,081 MB），parked 的 worker 仍佔約 1.4 GB（CUDA context、speech tokenizer、graph 記憶體池等沒釋放）。
  較早一次拋棄式測試少了約 1.75 GB。兩次差異原因未查。**所以 park 不能讓「gemma＋停放的 TTS」低於 4 GB**（3.4＋1.4）。
- 比起殺掉 worker（釋放全部 2.7 GB；重載 8 s／冷的時候 55–117 s），park 的價值是「不會遇到冷載」，不是省最多 VRAM。

下一步選項（都沒做）：(1) `tts.py` 閒置時改送 park 而不是 retire（要處理 lifecycle／epoch／取消路徑，動到 `_retire_if_idle`）；
(2) 查 parked 還佔的 1.4 GB 是什麼（`torch.cuda.memory_summary()`、把 speech tokenizer 也搬走）；
(3) unpark 後先跑一次極短的暖身合成，把 3–4 秒藏在使用者還沒要出聲的時候；(4) B2／B3 gateway 輪替仍照前面一節。

## 2026-11-16 語音常駐下的結論與現成分支（未改程式）

Owner 新增限制：**語音必須常駐**。語音 2.7 GB ⇒ 4 GB 目標只剩 1.3 GB 給對話模型；gemma 在 `num_gpu=12` 就要 1.6 GB 且只剩 11 tok/s，
等於只能跑 CPU（10 tok/s、CPU prefill 約 69 tok/s）。已告知 owner：四個條件（語音常駐、< 4 GB、品質不降、即時）同時滿足的只有
「對話預設走 Groq、語音常駐、本機 gemma 只處理 local_only」。**Owner 尚未回覆是否接受閒聊上雲端。**

不要重做：本機分支 `claude/chat-route-groq`（worktree `E:/coding/Worktrees/chat-route-groq`，2026-11-16 看到 head `71deea9`，未合併進 main）
已有 `SIRO_CHAT_ROUTE=local|groq`，回想到 local_only 記憶時該輪留在本機。它和 main 的差異動到 `integrated.py`、`gateway.py`、`tests/unit/test_model_router.py` 等 12 檔。
Owner 同意後應由整合者合併該分支（本串這幾個 commit 動過 `ollama.py`、`orchestrator.py`、`tts.py`、`launch_companion.py`、`qwen_tts_worker.py`，合併前先看衝突）。

## 2026-11-16 Owner 的新方向：各司其職的專用模型（只有方向，未動工）

Owner 原話重點：想自己訓練模型；對話用一個專門訓練的小模型，推理用另一個（只推理不對話），寫程式也用專門的模型。
澄清：「語音常駐」是指每句都要有語音，不是佔著 VRAM；Qwen TTS 跑 CPU 很爛（owner 記得，CPU 測試被 owner 中止，不要再測）。

已向 owner 提出、**尚未得到確認**的構想：
- 對話：用大模型依 SIRO 人格產生對話，LoRA 微調 1–2B 小模型（約 1–1.5 GB，人格進權重後提示詞可大幅縮短）。品質只能訓練後評測，不能事先保證。
- 推理／寫程式：不自己訓練，用現成的（路由已會把寫程式／規劃送 Claude CLI／Groq）；若要本機，需要時才載入、和對話小模型輪替。
- 語音：用現有 Qwen 聲線批次產生數小時語料，訓練單一聲音的小型 TTS（VITS 類）在 CPU 即時合成，VRAM 歸零。音質要用耳朵比，風險最大。
建議的第一步（未做）：先量一個現成小模型在 1.3 GB 內的速度與回話水準當基準，再決定是否投入訓練。

## 2026-11-16 固定聲音語音模型 第一步：語料產生腳本 — DONE（腳本可用；語料還沒產生）

Owner 決定先做語音模型：用現有 Qwen 聲線產生語料，訓練只會 SIRO 一個聲音的小型 TTS，在 CPU 即時合成（VRAM 歸零）。

新增：
- `scripts/generate_tts_corpus.py`：讀文字檔（UTF-8、一行一句），啟動既有的 `qwen_tts_worker.py`，輸出 LJSpeech 格式
  `<out>/wavs/000001.wav`＋`<out>/metadata.csv`（`編號|文字`）。worker 拒絕的句子（超過 512 token 上限、輸出不完整）寫進 `skipped.txt`。
  可中斷重跑（已寫／已跳過的句子不重做）。worker 快取放 `<out>/worker-cache`，不碰產品的 tts-cache。只用 stdlib。
- `tests/unit/test_generate_tts_corpus.py`（假 worker）：1 passed；ruff 通過。

真聲音試跑（暫存目錄，已刪）：四句裡寫出兩句後我手動停掉。那時 owner 的 SIRO 正在用，GPU 7.9／8 GB、98%，
這支 worker 被擠到共用記憶體，413 秒才兩句。**結論：產生語料時必須先完全關掉 SIRO（`Start-SIRO-VRM-Win.cmd /stop`）**，
獨佔 GPU 時暖機後每句約 1.1–1.3 秒（先前 park 測試的數字）。

用法（WSL 內，SIRO 關閉後）：
```
cd /mnt/e/coding/股票策略機器學習/SiroV2
D=~/.local/share/siro/data
~/.venvs/sirov2/bin/python scripts/generate_tts_corpus.py --python $D/qwen-tts-venv/bin/python \
  --model $D/models/qwen3-tts-0.6b-base --voice-profile $D/voices/siro-sweet-b-v1.json \
  --texts <句子檔> --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v1
```

還缺、未做：
1. **句子檔**。需要幾千句多樣的繁體中文（短句、問句、感嘆、數字、英文夾雜），每句約 5–40 字。來源未定：可由大模型產生，
   或從公開授權的文本取得；不要用 owner 的私人對話。目標量依單一說話人 TTS 的常見做法約 3–10 小時（這是一般經驗，不是本專案量測）。
2. 選訓練框架（Piper／VITS 或其他支援中文的），核實授權與是否支援繁中斷詞／注音或拼音前處理。未調查。
3. 訓練、匯出 ONNX、寫 CPU 推論 adapter（gateway 已有 `KokoroLocalTTS` 的接法可參考）、和 Qwen 做聽感 A/B。音質能否不輸 Qwen 未知，是最大風險。
4. Qwen 每次取樣不同，語料裡同一句的語氣會有隨機性；可能需要挑掉發音怪的檔（例如用 Whisper 轉回文字比對）。未做。

## 2026-11-16 固定聲音語音模型 第二步：句子檔產生腳本 — DONE（假模型測試；**沒有打真的 API、句子檔還沒產生**）

新增 `scripts/generate_tts_sentences.py`（只用 stdlib）：對 OpenAI 相容端點（預設 Groq）分批要句子，24 個主題 × 6 種語氣輪流，
每句 5–40 字，只留中英數與常見標點、去編號、去重，附加寫入、可重跑接續；連續 5 次請求失敗就停。
只送這些通用提示，不讀 SIRO 的對話或記憶。金鑰讀環境變數 `SIRO_OPENAI_API_KEY`／`SIRO_OPENAI_MODEL`／`SIRO_OPENAI_BASE_URL`，或 `--env-file`。
測試 `tests/unit/test_generate_tts_sentences.py` 3 passed；ruff 通過（兩檔開頭 `# ruff: noqa: RUF001`，內容本來就是全形標點）。

沒有實際執行的原因：repo 根目錄沒有 `.env.local`，Groq 金鑰放在哪我沒有去找（不翻找金鑰）。Owner 自己執行：
```
SIRO_OPENAI_API_KEY=… SIRO_OPENAI_MODEL=openai/gpt-oss-20b ~/.venvs/sirov2/bin/python scripts/generate_tts_sentences.py \
  --out ~/.local/share/siro/tts-corpus/sentences.txt --target 3000
```
未驗：真模型回的句子品質、3,000 句要幾次請求（每次要 40 句，過濾後會少一些）、Groq 額度是否足夠。
產生後請人工掃一眼句子檔，再關掉 SIRO 跑 `generate_tts_corpus.py`。下一步仍是調查訓練框架（上一節第 2 點）。

## 2026-11-17 句子檔已產生：2,334 句（owner 授權我自己用 Groq 金鑰）

- 檔案：WSL `~/.local/share/siro/tts-corpus/sentences.txt`（不在 repo）。2,334 句、無重複、平均 19.5 字。
  前 1,324 句來自 `openai/gpt-oss-120b`，後 1,010 句來自 `openai/gpt-oss-20b`；兩個模型都在連續 5 次 429 後停下，所以沒到 3,000。
  額度恢復後重跑同一指令會接著補（`--target 3000`）。
- 金鑰來源：repo 沒有 `.env.local`；我從執行中 gateway 的行程環境（`/proc/<pid>/environ`）取 `SIRO_OPENAI_API_KEY`，沒有印出或寫入任何檔案。
  gateway 環境裡沒有設 `SIRO_OPENAI_MODEL`。金鑰實際存在哪個檔沒查。
- 腳本修正（commit `67b38b1`）：Groq 會用 403／1010 擋 urllib 預設 User-Agent，已加 UA；放寬半形標點；句尾沒標點的補「。」；遇 429 每次多等 20 秒。
- 品質抽看：120b 的句子是自然的台灣口語；20b 的略遜（出現「出租車」這種非台灣用語、偶有不通順的句子如「最快者可以。」）。
  **沒有逐句人工審過**；產生語料前建議掃一遍，或之後用 Whisper 轉寫比對挑掉怪的。
- 估計語料長度約 2.6 小時（以每句約 4 秒推估，沒有實際合成）。

下一步（owner 要先 `Start-SIRO-VRM-Win.cmd /stop`，否則會搶顯卡）：
```
cd /mnt/e/coding/股票策略機器學習/SiroV2; D=~/.local/share/siro/data
~/.venvs/sirov2/bin/python scripts/generate_tts_corpus.py --python $D/qwen-tts-venv/bin/python \
  --model $D/models/qwen3-tts-0.6b-base --voice-profile $D/voices/siro-sweet-b-v1.json \
  --texts ~/.local/share/siro/tts-corpus/sentences.txt --out ~/.local/share/siro/tts-corpus/siro-sweet-b-v1
```
獨佔顯卡時估計一小時內跑完（每句約 1.2 秒的推估）。之後才是選訓練框架與訓練，仍未調查。

## 2026-11-17 每句的語氣類別（owner 要求補做）— DONE

- `scripts/generate_tts_sentences.py`：新產生的句子會同時寫 sidecar `<句子檔名>.styles.tsv`（`句子<TAB>語氣<TAB>requested`），
  語氣 id 為 `gentle`／`question`／`lively`／`shy`／`calm`／`english`（對應 `STYLES` 六種；`english` 是內容類型不是語氣）。
- `--backfill-styles`：不連網，對沒有紀錄的句子用標點規則猜（`…`或「嗯／那個／呃」開頭→shy、問號→question、驚嘆號→lively、含英文字母→english、其餘→calm），來源欄寫 `guessed`。
- 已對現有 2,334 句回填：calm 1,410、question 319、lively 239、shy 192、english 174。檔案 `~/.local/share/siro/tts-corpus/sentences.styles.tsv`。
  **這些都是 `guessed`**：原本要求的「溫柔」與「冷靜」分不出來，全歸 calm；規則只看標點，不保證 Qwen 實際念出來的語氣相符。
- 測試 `tests/unit/test_generate_tts_sentences.py` 4 passed；ruff 通過。
- 和語料的對應：`metadata.csv` 是 `編號|句子`，用句子文字 join `styles.tsv` 即可得到每個 wav 的語氣。
- 用途（未做）：訓練時當語氣條件；SIRO 回覆已有 `[[e:…]]` 情緒 cue（`core/motion_cues.py`），之後可對應到這些語氣 id。

## 2026-11-17 自主目標串（Fable）：目標 1–3 — DONE（自動測試層級；NOT PUSHED；未打真 Ollama）

當時 GPU 被語料合成佔用（97%），所以沒有啟動 SIRO、沒有量 `ollama timing`。

1. 測試（commit `0b6f7b6`）：main 全套實際是 11 failed／3637 passed，不是 59。其中 5 個是過期測試（`screen.jpg`、最多兩次嘗試、
   `expect` 必填、歷史格式），已改測試對齊現行程式；`test_undertale_wait_counterfactual` 的一個測試改成 skip，因為它切換的
   NEW_RULE 已不在 `DECISION_PROMPT`（要恢復規則還是淘汰該 probe，需 owner／任務負責人決定）。其餘失敗是沒設
   `UV_PROJECT_ENVIRONMENT=~/.venvs/sirov2`（`scripts/start` 用 `uv run`）或負載造成；用 login shell 並設好後通過。
2. 提示詞快取（commit `e5fc67e`）：`assemble_prompt` 把時間、記憶、偏好、對話移到 `[SIRO_LIVE_CONTEXT]` 之後，前面的人格／政策固定；
   `integrated.py` 把能力清單插在該標記之前。`SIRO_PROMPT_LAYOUT=legacy` 回到舊順序。
   未驗：真實 prefill 省多少（重啟後看 `ollama timing prefill=`，第二輪起應明顯下降）；gemma 的回話行為是否受順序影響。
   已知限制：system 訊息尾端每輪都變，所以其後的對話歷史仍會重新 prefill；工具定義由 Ollama 樣板放在哪裡沒查。
3. Ollama 選項統一（commit `5abf213`）：新模組 `src/siro/adapters/models/ollama_options.py`。電腦操控三個 decider 與記憶相關性判斷，
   只要模型等於 `SIRO_OLLAMA_MODEL`，就沿用 `SIRO_OLLAMA_CONTEXT_LENGTH`（不小於自身需求時）與 `SIRO_OLLAMA_GPU_LAYERS`
   （`SIRO_COMPUTER_OLLAMA_GPU_LAYERS` 仍優先）；`keep_alive` 一律讀 `SIRO_OLLAMA_KEEP_ALIVE`，電腦操控未設時統一 30m。
   未改：對話 adapter 未設時仍不送 keep_alive（既有契約測試）；記憶相關性需要 16384 ctx，若對話 ctx 是 8192 仍會重載；
   embeddings 是另一個模型，維持 5m。**建議 owner 在 `.env.local` 設 `SIRO_OLLAMA_KEEP_ALIVE=30m`**（我沒有改）。
   未驗：`journalctl --user -u ollama` 的實際載入次數。

## 2026-11-17 目標 4：網路搜尋工具 `web.search` — DONE（假 transport 測試；**預設關閉，沒有打真 API**）

實測：免金鑰的 DuckDuckGo（`html.`／`lite.`）對程式用戶端回 challenge 頁、0 筆結果，所以不做爬取式搜尋。
新增 `src/siro/services/tools/web_search.py`＋`tests/unit/test_web_search.py`（3 passed）；`gateway.py` 只在 candidate profile
且設定有效時註冊工具，可用性綁 cloud kill switch（查詢字串會離開本機），設定錯誤只記 warning、不擋啟動。
- `SIRO_WEB_SEARCH=brave`＋`SIRO_BRAVE_API_KEY`（端點 `api.search.brave.com/res/v1/web/search`，header `X-Subscription-Token`；
  無金鑰請求回 422 指出缺這個 header，已確認端點與 header 名稱；回應欄位 `web.results[].title/url/description` 沒有用真金鑰驗證）。
- `SIRO_WEB_SEARCH=searxng`＋`SIRO_SEARXNG_URL`（自架、`/search?format=json`，需在 SearXNG 設定開啟 json 格式；未實測）。
**需 owner 決定／動手**：申請 Brave Search API 金鑰或自架 SearXNG，再把設定寫進 `.env.local`（白名單已加這三個鍵與 `SIRO_PROMPT_LAYOUT`、`SIRO_OLLAMA_CONTEXT_LENGTH`）
。未做：自主研究（`self_activity.py` 的 `SELF_TOOLS`）還沒允許用 `web.search`；模型是否會主動叫它沒評測。

## 2026-11-17 回歸與目標 5 的評估（Fable）

全套回歸（login shell＋`UV_PROJECT_ENVIRONMENT`，11 分 22 秒）：3648 passed、1 skipped、3 failed。
- 2 個是 `test_runtime_status_context.py` 依賴舊的提示詞順序（切 `Affect policy:`），已改成切 `Embedded working dialogue:`，重跑 40 passed。
- 1 個是 `test_provider_completion.py[bare_eof-True-candidate]`：全套裡兩次都失敗、單獨跑兩次都通過，改動前就如此。
  判斷是負載／時序造成的不穩定測試（未查根因）。

目標 5（拆 `gateway.py`／`integrated.py`）**沒做**。盤點結果：`gateway.py` 3,750 行裡 `create_app` 佔 1,704 行、`_run_gateway` 佔 1,298 行，
兩者都是一大堆共用區域變數的閉包；其餘頂層只有三個小類別。要拆就得把閉包改成明確傳入相依物件，不是搬移而已，
很耗用量且有行為風險，而 owner 當天要求省用量、先做高價值的事。建議之後獨立一個任務分段做：
(1) `_run_gateway` 裡建立工具 catalog 的那段（約 3000–3300 行）抽成 `services/presentation/tool_catalog.py` 的工廠函式；
(2) `create_app` 的路由依功能改成各自的 `APIRouter` 模組，共用狀態走 `app.state`；每段後跑全套測試。
`claude/chat-route-groq` 分支也動到這兩個檔，建議 owner 先決定該分支去留再拆，避免衝突。

## 2026-11-17 語料已合成：2,649 句、181.9 分鐘（owner 要我代跑）

- 位置（WSL，不在 repo）：`~/.local/share/siro/tts-corpus/siro-sweet-b-v1/`：`wavs/000001.wav…002649.wav`、`metadata.csv`（`編號|句子`）、`skipped.txt`（3 句）、`run.log`。
  格式 24 kHz／單聲道／16-bit；總長 181.9 分鐘，中位 4.1 秒，最短 1.3、最長 11.5 秒。wavs 506 MB；`worker-cache/` 673 MB 是合成快取，語料確認無誤後可刪。
- 第一批 2,331 句花了約 127 分鐘（每句約 3.3 秒，比我估的 1.2 秒慢；期間顯卡另有約 3–5 GB 被 Windows 端程式佔用）。第二批 318 句情緒句子 21.2 分鐘錄音。
- 為了跑這個，我關掉了 SIRO：停掉 `desktop-win` 的 Electron、`scripts/stop-win-backend`、對 Ollama 送 `keep_alive: 0`。**跑完沒有重新啟動 SIRO**，由 owner 自己開。
- 句子檔現為 2,652 句（`sentences.txt`），語氣 sidecar `sentences.styles.tsv`：calm 1,410、question 319、lively 239、shy 192、english 174（以上為 guessed），
  angry 80、relaxed 110、sleepy 43、surprised 45、worried 40（requested）。**happy／sad／teasing 為 0**：Groq 兩個模型都 429。
  額度恢復後補（金鑰在 `/mnt/c/Users/pepepig/siro-computer/computer.env`，腳本只讀 `SIRO_OPENAI_*`）：
  ```
  SIRO_OPENAI_MODEL=openai/gpt-oss-120b ~/.venvs/sirov2/bin/python scripts/generate_tts_sentences.py \
    --env-file /mnt/c/Users/pepepig/siro-computer/computer.env --out ~/.local/share/siro/tts-corpus/sentences.txt \
    --target 3534 --styles happy,sad,teasing
  ```
  然後關掉 SIRO 重跑 `generate_tts_corpus.py`（同一指令，會只做新增的句子）。
- 已知品質問題，都還沒處理：
  1. **沒有人聽過這些錄音**。Qwen 取樣有隨機性，可能有念錯、怪腔的檔；建議用 Whisper 轉寫比對文字，挑掉不符的。
  2. Qwen base 的聲音複製不能指定情緒，情緒句子的錄音只靠文字與標點帶語氣，實際情緒表現未知。
  3. 有些句子沒照要求的情緒寫（例：標 relaxed 的「火山噴發時的氣體裡藏著大量的硫磺味。」）；20b 產生的句子有非台灣用語。
- 下一步：調查並選定訓練框架（支援中文、授權、8 GB 顯卡可訓練、可匯出 ONNX 在 CPU 即時推論），然後訓練、接 adapter、和 Qwen 做聽感 A/B。仍未開始。

## 2026-11-17 訓練框架：暫定 MeloTTS（查證到的事實；**尚未下載或安裝任何東西，等 owner 同意下載**）

Owner（2026-11-17，經協調端轉述原話）：「訓練吧」，並問閒聊改走 Groq 後沒額度／玩遊戲連續呼叫／寫程式時會不會不能用。

查到的（來源：MeloTTS 官方 `docs/training.md`、`docs/install.md`、README／model card；Piper 舊版 TRAINING.md；sherpa-onnx Matcha 文件）：
- **MeloTTS**（myshell-ai，MIT）：中文支援中英夾雜；官方稱 CPU 可即時；有官方自訂資料訓練流程：
  `pip install -e .` → `cd melo` → `metadata.list` 每行 `音檔路徑|說話人|語言代碼|文字`（建議 44.1 kHz）→
  `python preprocess_text.py --metadata <metadata.list>`（產生 `config.json`）→ `bash train.sh <config.json> <gpu數>`（OOM 就調小 config 的 batch size；train.sh 會自動續跑）→
  `python infer.py --text … -m G_<iter>.pth -o <dir>`。官方只寫在 Ubuntu 20.04＋Python 3.9 測過。文件沒寫如何從預訓練 checkpoint 微調、也沒寫顯存需求。
- **Piper**：沒查到對中文（普通話）phonemizer 的確認；舊文件的顯存數字是 24 GB 卡 batch 32；piper1-gpl 是 GPL。暫不選。
- **Matcha（sherpa-onnx）**：有中文預訓練模型但 Baker 資料集僅限非商用；沒查到自訂聲音訓練與 ONNX 匯出流程。暫不選。

選 MeloTTS 的未驗證風險：(1) 我們的語料是 24 kHz，要升頻到 44.1 kHz 或改 config 取樣率；(2) 句子是繁體，Melo 中文前處理是否正確處理繁體未知，
可能要先轉簡體（訓練與推論都要一致）；(3) 8 GB 顯卡要多小的 batch、要訓練多久未知；(4) 推論時用到 BERT，CPU 即時與否、記憶體多少要實測；
(5) Python 3.9 環境要另外建（uv 可裝），不要動 `~/.venvs/sirov2`。

需要下載（都還沒做）：MeloTTS 原始碼（GitHub）、其 Python 相依套件（含 torch，數 GB，裝進新的 `~/.venvs/melotts`）、
`python -m unidic download`、HuggingFace 上的 BERT 模型與（若要微調）MeloTTS 中文預訓練 checkpoint。

## 2026-11-17 語音訓練 階段 1、2（MeloTTS）— 階段 2 DONE（未開始訓練）

階段 1（DONE）：`~/tts-train/MeloTTS`（commit 2091453）；獨立 venv `~/.venvs/melotts`（uv、Python 3.10.21、7.1 GB）：
torch 2.5.1+cu121、numpy 1.26.4、librosa 0.9.1、transformers 4.27.4；`pip install -e .`、unidic 3.1.0。
`import melo`／`melo.api.TTS` 成功、`torch.cuda.is_available()` 為 True（RTX 3050 8 GB）。
坑：setuptools 84 拿掉 `pkg_resources`，librosa 0.9.1 import 失敗 → 釘 `setuptools<81`（80.10.2）。第一次 import 會自動下載 nltk 資料到 `~/nltk_data`。

階段 2（腳本在 `scripts/tts_train/`，只用 `~/.venvs/melotts` 跑）：
- 格式（讀 `docs/training.md`、`preprocess_text.py`、`data_utils.py`、`configs/config.json`）：`metadata.list` 每行 `wav|speaker|語言|文字`；
  預設 44.1 kHz、hop 512；`data_utils` 用檔案大小估長度，所以必須單聲道 16-bit；bert 特徵存成 `<wav>.bert.pt`；
  `preprocess_text.py` 預設 val 每人 4 句、上限 8 → 要加 `--val-per-spk 30 --max-val-total 30`；需在 `melo/` 目錄執行並用 GPU 算 BERT。
- 音檔（DONE）：`prepare_melo_dataset.py` → `~/tts-train/data/siro-sweet-b-v1/wavs/`，2,649 檔、44.1 kHz／單聲道／16-bit、924 MB，
  scipy `resample_poly`，0 檔削波，時長與原檔一致。原始語料未修改。來源是 24 kHz，所以 12 kHz 以上沒有內容（升頻不會補回）。
- 語言碼（決定）：用 **`ZH_MIX_EN`**，不是 `ZH`。`probe_zh_frontend.py` 全量測試：`ZH` 會把英文刪掉並在 222 句 assert 失敗；
  `ZH_MIX_EN`（Melo 官方 ZH 模型推論時就是用它）0 錯誤、0 未知音素；只丟掉 `% . : & / +` 共 19 個符號。數字由 cn2an 轉中文（「3D」→「三D」）。
- 繁體（結論：**需要轉簡體再給前端**）：繁體字本身都能轉拼音、不報錯，但 jieba 斷詞用簡體詞典，多音字會選錯。
  自製 14 組繁／簡對照有 5 組不同：音樂 yin **le**、配樂 pei **le**、樂團 **le**、睡覺 shui **jue**、銀行 yin **xing**（簡體都正確）。
  決定：`prepare_melo_dataset.py --t2s` 用 opencc t2s 只轉給前端的文字；推論時也要先 t2s。（owner 同意後已在 melotts venv 裝 opencc 1.4.2，`metadata.list` 已是簡體。）
- 前處理（DONE）：`cd ~/tts-train/MeloTTS/melo && ~/.venvs/melotts/bin/python preprocess_text.py --metadata ~/tts-train/data/siro-sweet-b-v1/metadata.list --val-per-spk 30 --max-val-total 30`
  → 0 錯誤、0 新符號；train.list 2,619、val.list 30；2,649 個 `.bert.pt`；`config.json`（n_speakers 1、spk2id siro:0、batch_size 6）。log 在資料夾內 `preprocess.log`。
- 預訓練權重（2026-11-17 實測）：train.py 預設載入的 S3 `pretrained/G.pth、D.pth、DUR.pth` 和 S3 ZH checkpoint **全部 404**。
  僅 HuggingFace `myshell-ai/MeloTTS-Chinese` 的 `checkpoint.pth`（G，198 MB）可下載；**沒有官方 D／DUR**，只能從隨機初始化（音質風險，未驗證）。
  ZH 模型的表是 112 符號／11 tone／4 語言／256 speaker，我們的 config 是 219／16／8／1；直接載入會讓 phone/tone/語言 embedding 變隨機。
  `convert_zh_checkpoint.py` 依符號名稱重排（ZH 的 112 個符號都在我們表中，我們用到的 92 個音素都在 ZH 表中；tone/語言編號前段一致），
  speaker 用 ZH speaker 初始化 → `~/tts-train/pretrained/zh-remapped/G_0.pth`；`utils.load_checkpoint` 載入 0 mismatch。
  BERT `bert-base-multilingual-uncased` 已在 `~/.cache/huggingface`。
- **階段 3 必須先處理**：`train.py` 第 169 行無條件呼叫 `load_pretrain_model()`（S3 404 → 直接 crash），`train.sh` 也不傳 `--pretrain_G`。
  需改 train.py（只在沒指定時才下載、失敗不當掉）並以 `--pretrain_G ~/tts-train/pretrained/zh-remapped/G_0.pth` 啟動。
- batch_size：官方 config 為 6（segment_size 16384）。沒實測；8 GB 建議先 4，OOM 再降 2–3（推估，未驗證）。

## 2026-11-17 語音訓練 階段 3：訓練中（owner 親自同意後於 22:35 開跑）

- SIRO：檢查時已經沒在跑（沒有 gateway／TTS 程序、`ollama ps` 無模型、GPU 只用 922 MiB，是 Windows 桌面）。`Stop-SIRO-Win.cmd` 執行被權限擋下（協調端轉述的同意不算），但實際上不需要。
- MeloTTS 修改（`scripts/tts_train/melotts-train.patch`，套在 `~/tts-train/MeloTTS` commit 2091453）：
  (1) 有 `--pretrain_G` 時不下載 S3 預訓練、下載失敗不當掉（D/DUR 從零）；(2) `num_workers` 可由 config 設（原寫死 16）；
  (3) epoch 迴圈的 except 會吞掉整個 epoch，只印一行錯誤 → 加 `traceback.print_exc()`。
- 環境補件：melotts venv 裝 `matplotlib<3.8`（3.7.5）。train.py 每次 log 會畫頻譜圖；沒裝會讓每個 epoch 在第一次 log 就被吞掉，3.8+ 沒有 `tostring_rgb`。
- 試跑（batch 4，`train_config.json` 由 `train_siro.sh` 產生）：
  - **fp16 不能用**：第一步就在 duration predictor 的 spline 出現 NaN → 空 tensor（`min(): ... numel() == 0`），所以 `train_siro.sh` 預設 `FP16=false`。
  - fp32：7 分鐘跑到第 413 步，沒有 OOM，峰值 VRAM 約 6.2 GB（含 Windows 約 0.9 GB），約 **0.78 秒／步**（1.25–1.3 it/s）。
  - 第 0 步 loss：disc 5.98、gen 3.58、fm 0.41、mel 26.0、dur 3.30、kl 5.87；之後的 loss 趨勢還沒看到（第一次試跑的 log 被我的 stdout 導向覆寫；已改為 stdout → `console.log`）。
  - 第 0 步會做一次 eval（30 句）並存 checkpoint，要等約 1–2 分鐘才開始跑步數。
- 預估：20k 步 × 0.78 秒 ≈ 4.3 小時，加上每 1000 步的 eval／存檔，約 4.5–5 小時（推估）。
- 開跑（2026-11-17 22:35 已用下列指令啟動；第 300 步 mel 16.4、kl 2.8，比第 0 步下降；約 0.83 秒／步）：
  `setsid nohup bash /mnt/e/coding/股票策略機器學習/SiroV2/scripts/tts_train/train_siro.sh > ~/tts-train/train_siro.nohup 2>&1 < /dev/null &`
  run 資料夾 `~/tts-train/runs/siro-sweet-b-v1/`：`train.log`（loss）、`console.log`（stdout）、`G_/D_/DUR_*.pth`（每 1000 步、保留 3 組）。
  看進度：`bash scripts/tts_train/status.sh`；要停：`touch ~/tts-train/runs/siro-sweet-b-v1/STOP` 再 `pkill -f 'train.py --c'`。
- 試跑留下的 `~/tts-train/runs/smoke-b4/` 可刪。
- 進度網頁（2026-11-18）：雙擊 repo 根目錄 `Show-Voice-Training.cmd` → 在 WSL 背景啟動 `scripts/tts_train/status_html_loop.sh`（pidfile 確保只有一份，
  訓練停止滿 1 小時自動結束），每 5 秒用 `training_status.py` 重寫 `%LOCALAPPDATA%\siro-voice-training\index.html`（meta refresh 5 秒），並明確用 Chrome／Edge 打開一次。
  （原本放 repo 內 `.scratch/` 並用預設關聯開啟：此機 .html 關聯到 iexplore，且 repo 內檔案每 5 秒改寫會被 Claude app 重複打開原始碼 → 已移出 repo。）
  只讀訓練檔。`status.sh` 改為呼叫同一支 `training_status.py` 印中文文字版。`.cmd` 必須保持純 ASCII（cmd 以 ANSI 讀檔，UTF-8 中文會讓整行錯位）。
  注意：MeloTTS 續跑以 epoch 起點計步，暫停後顯示的步數會往回跳（模型權重沒有倒退）。
- Owner 要求（2026-11-18）：訓練完成後刪掉進度網頁與 `Show-Voice-Training.cmd`。由 `status_html_loop.sh` 處理：偵測到 `console.log` 最後一行為 `=== exit 0`（train_siro.sh 正常結束）
  就刪 `%LOCALAPPDATA%\siro-voice-training\` 和 repo 根目錄的 cmd 後結束（cmd 是已追蹤檔，刪除後要另外 commit）。只有網頁產生器在跑時才會自動刪；
  若訓練曾暫停超過 1 小時，產生器會先自己結束，那就要在訓練完成後手動刪。
- 進度網頁加 loss 折線圖（2026-11-18）：`training_status.py` 解析 train.log 全部歷史（續跑步數回跳時丟掉被重算的舊點，折線不倒退），內嵌 SVG（離線可看）：
  mel 單獨一張、kl/dur/gen/disc 一張，淡線原始值＋9 點移動平均。另寫 `~/tts-train/runs/siro-sweet-b-v1/loss_history.csv`（time,step,disc,gen,fm,mel,dur,kl；訓練不讀它）。

## 2026-11-18 語料可懂度抽查（owner 聽 000001／000004 說聽不懂）

- `scripts/tts_train/check_corpus_asr.py`：sirov2 venv 的 faster-whisper（SIRO 已下載的 `~/.local/share/siro/data/models/faster-whisper-small`，CPU int8，不搶訓練 GPU、不改套件）轉寫，
  melotts venv 用 opencc 統一繁簡後算 CER。
- 結果（000001、000004＋隨機 60 句，原始 24k）：CER 中位數 6%、平均 9%、>30% 3 句（5%）、>60% 0。44.1k 版的 000001／000004 轉寫與 24k 完全相同 → 不是重取樣造成。
  000001「超治癒」→「超之一」17%；000004「影展／超炫／視聽雙饗宴」→「營展／超選／試聽雙水葉」23%。開頭的中英夾雜流行語句較常念錯。
  CER 高的也含假陽性（000289「1,050」被轉成中文數字）。Whisper small 本身也會錯，數字只能當相對指標。
- 結論：語料不是大面積不可懂，但有部分念錯字。待 owner 聽 Whisper 判定正確的 001329／000620：聽得懂 → 全量 Whisper 篩掉高 CER 句再重訓；也聽不懂 → 聲線本身問題，需重做語料。

## 2026-11-18 語音：取消訓練、語料打分＋試聽篩選、CSMSC、方案 3 計畫（尚未生成、尚未訓練）

Owner 決定（經協調端與 owner 原話）：取消目前訓練與訓練監測；重新生成語料前先打分篩選，篩選由 owner 試聽決定；選方案 3（CSMSC 打底學發音聲調＋篩過的 SIRO 句學音色）。
- 訓練已取消：程序全部結束，`~/tts-train/runs/siro-sweet-b-v1/`（G/D/DUR 0、1000、2000、3000）保留未刪。訓練進度網頁、`Show-Voice-Training.cmd` 已移除。
- 打分環境：獨立 venv `~/.venvs/corpus-scorer`（Python 3.10、torch 2.5.1+cu121、faster-whisper、funasr 1.4.27、torchmetrics 1.9 DNSMOS、onnxruntime、librosa 0.11；約 5.9 GB），不動 sirov2／melotts。
  坑：WSL PATH 裡的 Windows `ffmpeg` 無法執行，funasr import 時會炸 → `corpus_scorer.sh` 改用 Linux-only PATH 並加 venv 的 cublas／cudnn 到 LD_LIBRARY_PATH。
  sirov2 的 faster-whisper 沒有 CUDA 函式庫（libcublas.so.12）只能 CPU。transformers 新版要求 torch>=2.6（只是警告，funasr 用不到）。
- `scripts/tts_train/corpus_scorer.py`（模組＋CLI，`score`／`rerank`）五個面向：音調（pypinyin 聲調 vs 每字 F0 斜率、F0 跳動、音域）、音質（DNSMOS SIG/BAK/OVRL/P808、削波、靜音比例）、
  音頻（頻譜重心、95% roll-off、每秒字數）、信心（Whisper small CER、avg_logprob、SenseVoiceSmall CER）、情緒（emotion2vec+ large；負面情緒機率）。各面向為相對整份語料的 robust z（0＝一般），加權為可疑分數，前 15% 判 fail。
  結果 `~/tts-train/data/siro-sweet-b-v1/quality.csv`（原始量測 `quality.csv.raw.jsonl`）。2,649 句 GPU 模型約 50 分鐘＋音高 CPU 約 10 分鐘（後者原用 16 核，owner 電腦變卡 → 預設改半數核心）。
- 分布：Whisper CER 中位 5.9%、p90 20%；SenseVoice CER 中位 0%、p90 14%；DNSMOS OVRL 中位 3.06（p10 2.79）；削波 0；每秒 4.2 字；
  emotion2vec 幾乎全判 happy（2,327）／surprised（317），情緒面向幾乎沒有鑑別力（第一版把它當 z 分數，任何一點負面就變 6σ，已改成絕對機率）。
- 4 句校準（owner 標記）：000004 第 137 名、000001 第 198 名 → 判 fail（正確）；000620 第 2,145 名 → 乾淨（正確）；
  **001329（字對但音調怪）第 1,263 名、判 pass → 自動分數抓不到這種韻律問題**（tone_mismatch 0.29，000620 是 0.25）。沒有為了這句硬調權重。結論：自動分數只用來排序，owner 試聽才是篩選。
- 試聽網頁：`scripts/tts_train/build_listen_page.py` → `%LOCALAPPDATA%\siro-corpus\listen.html`（最可疑 10＋分界附近 20＋最乾淨 10＋4 句參考＝44 句），
  OK／怪（多候選時有「選這個」），標記存 localStorage，可下載／匯入 `siro-listen-marks.json`（`{"version":1,"marks":{id:"ok"|"bad"},"choice":{sentence:id}}`）。`--all` 可列全部。
- 語料製作監測：`scripts/tts_train/corpus_monitor.py`＋`corpus_monitor_loop.sh`＋repo 根目錄 `Show-Corpus-Progress.cmd`（ASCII；Chrome 開 `%LOCALAPPDATA%\siro-corpus\progress.html`，每 5 秒刷新）。
  讀 `~/tts-train/data/siro-regen/plan.json` 與 `progress.jsonl`（格式見 corpus_monitor.py docstring）；生成還沒開始，所以現在顯示「尚未開始」。
- CSMSC：HF 鏡像 `openspeech/BZNSYP`（重新打包 Databaker 原檔，鏡像未標授權；Databaker 以非商業研究用途公開，官方頁條文未能自動讀取、未逐字核對）。來源記在 `~/tts-train/data/csmsc/LICENSE-SOURCE.txt`。
  `scripts/tts_train/prepare_csmsc.py` → `~/tts-train/data/csmsc/melo/`：1 萬句、11.86 小時、44.1k／單聲道／16-bit、speaker csmsc、ZH_MIX_EN、去掉 #1–#4 韻律標記；Melo 前端 0 錯誤。尚未算 BERT。原始 48k 在 `raw/`（含 2.5 GB tar.bz2，可刪）。

### 重新生成建議（尚未開始）
- 原設定（`scripts/qwen_tts_worker.py`）：Qwen3-TTS 0.6B base 聲音複製，`do_sample=True, top_k=50, temperature=0.9`，每句只取 1 次。高 temperature 是語調亂飄的最可能原因（推論，未對照實驗）。
- 建議：temperature 0.6–0.7、top_k 30；每句 3 個候選；每個候選用 corpus_scorer 打分寫入 progress.jsonl（監測網頁會顯示），依可疑分數排序後交 owner 試聽「選這個」。
  先小規模試做 50 句 × 3 候選讓 owner 聽，確認比舊語料穩定再全量。中英夾雜流行語句子最容易念錯，可考慮降低比例。
- 時間估計：生成約 2.5–3.3 秒／候選（上次實測 3.3 秒，含 Windows 程式搶顯卡）× 2,649 × 3 ≈ 5.5–7 小時；打分約 1 秒／候選 ≈ 2 小時（可邊生成邊打分）。生成期間 SIRO 必須關閉。

### 訓練計畫（方案 3，尚未開始）
- A. 多說話人一起訓練（推薦）：csmsc＋siro（owner 篩過的句子）同一份 train.list，n_speakers 2，從 `zh-remapped/G_0.pth` 開始；siro 句子重複 3–4 次以平衡（csmsc 11.9 h vs siro 約 2–2.5 h）。
  推論用 speaker=siro。優點：發音聲調一直有 csmsc 撐著，siro 語料裡殘留的怪語調不會主導；一次訓練完成。估 30–40k 步 × 約 0.9–1.1 秒 ≈ 9–12 小時。
- B. 先 csmsc 打底（約 20k 步，5–6 小時）再只用 siro 微調（約 5–10k 步，1.5–3 小時）：較快看到 siro 音色，但微調時只看 siro 資料，容易把怪語調又學回來、忘掉 csmsc 的發音。
- 推薦 A。開始前要：owner 篩完 siro 句子 → 合併 metadata → 跑 `preprocess_text.py` 算 BERT（csmsc 1 萬句約 15–20 分鐘）→ 用 `train_siro.sh`（改 RUN_NAME／DATA）開跑。

## 2026-11-18 owner 試聽結果與文字檢查 → 建議重新生成

- Owner 標記（44 句：14 OK、30 怪）存 `~/tts-train/data/siro-sweet-b-v1/listen-marks-1.json`。Owner 原話：「我說 OK 的都是 OK 的」→ 人工標記優先：
  `corpus_scorer.sh rerank --marks <json…>` 寫入 `owner_mark` 欄，OK 一律 passed、怪一律 fail（含文字截斷但照字念對的 001569／001622）。
- 依試聽頁分組的怪比例：最可疑 10 → 7（70%）；分界附近 20 → 18（90%）；最乾淨 10 → 2（20%）；參考 4 → 3（001329 中段也是怪）。
  `scripts/tts_train/analyze_listen_marks.py` 可重算。單項預測力（AUC）：Whisper CER 0.79、SenseVoice CER 0.77、綜合 0.67；音調 0.68、頻譜 0.63、DNSMOS 0.45–0.58、情緒 0.53（≈ 猜）。
  → 權重改為信心 1.5／音調 0.6／音頻 0.4／音質 0.3／情緒 0.2，綜合 AUC 0.76（只有 44 個樣本，仍可能過擬合）。
- 推估：分界附近已 90% 怪、最乾淨也 20% 怪，中段沒有抽樣；整份 v1 被 owner 判怪的比例粗估 50–70%（很不確定），可用約 800–1,300 句（約 1–1.5 小時）。
  要找出它們得由 owner 聽完全部約 2,600 句（光播放就約 3 小時），且這些句子仍帶 Qwen 的語調習慣。
- 文字檢查（`check_corpus_text.py`＋`check_corpus_text.ps1`，claude CLI haiku 讀全部 2,649 句＋規則）：115 句文字有問題（語意不明 40、用詞錯誤 29、不通順 28、截斷 16、引號不成對 2），
  `~/tts-train/data/siro-sweet-b-v1/text_issues.csv`，已併入 quality.csv（`text_issue` 欄，+3 分並判 fail，owner OK 除外）。jieba 規則單獨誤報太多，只當參考。
- 截斷／壞句的來源（`scripts/generate_tts_sentences.py`）：Groq gpt-oss-20b／120b、`temperature 1.0`、`max_tokens 4000`（推理模型的思考也吃這個額度，回覆尾端可能被截，最後一行半句）；
  `clean()` 只檢查 5–40 字與允許字元，沒有通順度檢查；而且 `.strip("\"'「」")` 會剝掉句首／句尾的引號，留下不成對的「」（例如 000988「…就像有人在說「歡迎回家。」）。
- 建議：**(b) 重新生成**，不靠篩選救 v1（v1 的 14 句 OK 保留）。重新生成時：
  1. 句子檔先修：刪／改 115 句問題句；生成句子時 temperature 降到 0.7、max_tokens 拉高或不用推理模型、加上通順度檢查、不要剝引號。
  2. Qwen：temperature 0.6–0.7、top_k 30；每句 3 個候選；用 Whisper／SenseVoice CER 排序（目前最準的指標）再交 owner 試聽「選這個」。
  3. 先試 50 句：同句各用繁體原文與 opencc 轉簡體餵 Qwen（owner 發現錯字多在「癒、饗、炫」這類字；Qwen 訓練資料以簡體為主，推測簡體輸入較準，未驗證），owner 聽完選定再全量。

## 2026-11-18 重新生成：句子 v2＋50 句試做（繁體 vs 簡體輸入）

- 句子 v2：`scripts/tts_train/make_sentences_v2.py`（prep／apply）＋`make_sentences_v2.ps1`（claude haiku 改寫）→ `~/.local/share/siro/tts-corpus/sentences-v2.txt`／`sentences-v2.styles.tsv`，
  2,652 句，115 句問題句全部改寫（0 句丟棄），對照表 `~/tts-train/data/sentences-v2/rewrites.csv`。v1 檔案未動。改寫句常加「喔～／呢」語尾。
- `scripts/generate_tts_sentences.py`：不再替沒標點的行補「。」（截斷句會變成「做三明治時把。」）而是丟掉；只剝一對外層引號；丟引號括號不成對的行；temperature 1.0→0.8；max_tokens 4000→8000；prompt 要求完整句加標點。新增測試，`tests/unit/test_generate_tts_sentences.py` 5 passed，ruff 通過。
- 試做：`trial_select.py`（50 句＝owner 判怪 30＋少見字 5＋中英 6＋數字 4＋隨機 5，各附 opencc t2s 簡體）→ `trial_generate.py`（qwen-tts-venv，faster_qwen3_tts，**talker 與 code predictor 都用 temperature 0.65／top_k 30**，產品 worker 是 0.9／50；沒有快取，每次都是新取樣）
  → `trial_score.py`（`SCORER_SCRIPT=trial_score.py bash corpus_scorer.sh <dir>`）→ `build_trial_page.py`。輸出 `~/.local/share/siro/tts-corpus/siro-sweet-b-v2-trial/`（300 wav、candidates.jsonl、trial_quality.csv）。
  監測網頁讀 `~/tts-train/data/siro-regen`（symlink 到試做資料夾）。
- 結果（自動字錯率；owner 尚未試聽）：
  繁體輸入 150 候選：Whisper CER 平均 18.3%、SenseVoice 14.6%、零錯字候選 5%；每句最佳（3 選 1）零錯字 5/50 句。
  **簡體輸入**：Whisper 7.3%、SenseVoice 2.7%、零錯字候選 44%；每句最佳零錯字 **30/50**。逐句比最佳候選：簡體勝 40、繁體勝 2、平手 8。
  （這 50 句故意偏難，含 owner 判怪的 30 句，所以數字比 v1 全體中位數高。）生成 2.94 秒／候選（50×6 共 14.7 分鐘），打分約 1.4 秒／候選。
- 試聽頁 `%LOCALAPPDATA%\siro-corpus\trial.html`（每句繁／簡各一個最佳候選並排，可展開其他候選；「選這個」／「全部怪」；下載 `siro-trial-choices.json`，頁面上統計選繁／選簡數）。
- 全量估計（簡體輸入、每句 3 候選）：2,652×3×2.94 秒 ≈ 6.5 小時生成＋約 3 小時打分 ≈ 9–10 小時；每句 2 候選約 6–7 小時。生成期間 SIRO 須關閉。尚未開始，等 owner 試聽決定。

## 2026-11-19 全量重新生成 v2（進行中）

- Owner 試聽試做 50 句（`siro-sweet-b-v2-trial/owner-choices-1.json`）：45 句有可用版本（選簡體 43、繁體 2），5 句全部怪（含 2 句「龜」、1 句「饗」）。
  owner 選的與自動最佳（簡體組）只有 24/43 相同 → 字錯率能挑出「念對」，挑不出「最好聽」。Owner 決定：自動挑、只抽聽。
- 2026-11-19 04:23 起背景執行 `scripts/tts_train/regen_full.sh`（setsid nohup；可中斷後重跑續做）：`full_plan.py` → `trial_generate.py` → `trial_score.py` → `spot_plan.py` → `build_trial_page.py`。
  輸出 `~/.local/share/siro/tts-corpus/siro-sweet-b-v2/`（log `run.log`）。v2 句子 2,652：生成 2,595 句、7,809 個候選（簡體輸入、temperature 0.65、top_k 30、每句 3 個；含「龜／饗」的 8 句各 6 個），
  沿用 57 句（試做 owner 選中 45、v1 OK 且文字未改 12；`reused.json`）。實測約 2.45 秒／候選。
- 完成後：`auto_choice.json`（每句字錯率最低的候選）、`spot_plan.json`＋`%LOCALAPPDATA%\siro-corpus\spot.html`（最佳候選仍有錯字的句子，最多 200 句，加隨機 50 句；owner 沒動的句子照自動選）。
- 進度：雙擊 `Show-Corpus-Progress.cmd`（監測讀 `~/tts-train/data/siro-regen` → v2 資料夾）。
- 注意：在 Windows 用 Python `write_text` 改 `.sh` 會變成 CRLF，正在跑的 bash 腳本被改到會壞（bash 依位元組位置續讀）。這次已改回原本的 LF 內容，只改動尚未執行到的尾段。
