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
