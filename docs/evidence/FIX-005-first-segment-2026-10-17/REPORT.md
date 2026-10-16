# FIX-005 — NVIDIA 恢復後的原聲線真機複驗，2026-10-17

狀態：**GPU 功能、隔離前端實播與停止 PASS；FIX-005 保持 PARTIAL，速度體驗仍 FAIL**。本次 follow-up 沒有修改 production code。人工聽驗待 owner 回饋。不能以 CUDA 恢復或快取速度宣告語音體驗完成。

## 環境與測量邊界

使用者完成既有 `scripts/repair-nvidia-kernel` 後，`nvidia-smi` 認到 RTX3050 Laptop、driver595.99.02、4,096MiB；原 Qwen venv 的 Torch2.12.0+cu130 / CUDA13.0 實測 available=true。沒有停用 Secure Boot、改模型、改 reference、降低生成上限或使用 CPU 偷換量測。

暫停 managed8000 backend 避免另一個 Qwen owner；測量前沒有 Qwen 或 NVIDIA compute owner。沿用 [GPU-only harness](../FIX-005-first-segment-2026-10-16/verify_gpu_only.py)，current `QwenReferenceTTS` → current worker → 真 CUDA。所有樣本使用全新 temporary cache；舊、新 planner 只比較首段工作量，使用相同 current 模型、v1 聲線、SDPA 與生成設定。兩個故事變體交錯順序；小樣本、隨機生成，不作統計或速度 SLO 保證。

## 真 GPU 結果

| Case | 原文首段字數 | 實測等待 | 音訊長度 | Cache |
|---|---:|---:|---:|---|
| cold-short（含載入） | 22 | 20.104s | 5.20s | miss |
| 相同短句快取 | 22 | 0.019s | 5.20s | hit |
| 舊 planner 首段，故事1 | 56 | 21.648s | 12.80s | miss |
| 新 planner 首段，故事1 | 16 | 7.781s | 4.48s | miss |
| 新 planner 首段，故事2 | 16 | 10.109s | 5.60s | miss |
| 舊 planner 首段，故事2 | 56 | 21.694s | 12.96s | miss |

見 [gpu-measurements.json](gpu-measurements.json)。快取 bytes 另行逐位元組比對相等；不能把0.019s算作暖推論。新 planner 的16字經既有 `prepare_spoken_text` 補句尾標點後為17字，沒有省略內容。所有生成均 EOS=true、cap_reached=false。這只證明生成正常終止，不證明人耳逐字完整／自然度。

量測抽查只有同一個 owned worker；最後 close 後 returncode=-9、已 reap、無殘留，temporary cache已刪除，source起訖 SHA一致。這不是跨 process OS singleton 鎖，也不是全程 GPU PID 監控。生成 WAV 只留 ignored `.siro-data/verification/FIX005-first24-20261017`，未讀私人聊天或傳送音訊到雲端。

## 當前前端 → Gateway → CUDA → Native Audio

[serve_ui_probe.py](serve_ui_probe.py) 使用 current `create_app` / GatewayHub / QwenReferenceTTS / worker，current index 主 script bytes不變，只在前面加入既有 native Audio observer 及唯讀DOM觀察輸出。以 CUA 開啟隨機 loopback port，實際勾選語音、輸入合成驗收提示、按送出／停止；沒有用額外 Playwright程式操控 browser、呼叫隱藏 `playTts()` 或 mock Audio。

模型回覆是固定合成故事，body明示placeholder，不讀私人DB、不呼叫LLM／ASR／雲端。這是 **in-app browser 的真 Audio**；不能延伸為 GTK/WebKit桌寵、真provider或人耳驗收。

- 故事157字、三段：每段文字hash與current plan一致、全為cache miss、正常EOS；只有同一個worker，render依序，最多一段預取。
- 三個真 `playing → ended` 完成，playbackRate=1、無error；UI僅在最後ended後1ms顯示「全文朗讀完成（3/3 段）」。
- 此次cold首播18.789s；三段render18.718／28.731／31.510s，段間23.977／14.926s。**長文仍不流暢**，不能只宣稱較短首段有效就放行。
- 取消案例：檢查後到真正點擊之間，fresh第一段已生成並播放；實際取消的是**正在推論的第二段預取，同時停止第一段播放**。worker stdin-drain timestamp < 真按鈕click < CancelledError/reap完成；約0.517s回收，沒有回傳第二段WAV。不是「取消時還沒出現任何audio」測試。
- 後續87.527s觀察維持「朗讀已停止」，沒有任何click後新建Audio或第二段播放。沒有直接擷取第四個Audio的paused屬性，不能將此屬性標PASS；其未再產生ended事件與原stop清src路徑相符。
- 關閉測試tab、SIGTERM停止isolated server後，pending=0／active cleared／owned worker reaped／無殘留／server及listener關閉／control clients=0／temporary cache移除／production source hash起訖一致。

見 [browser-observations.json](browser-observations.json)（CUA回傳DOM事件的精簡抄錄）及 [ui-verification.json](ui-verification.json)（與worker記錄對時後的斷言結果）。完整synthetic worker報告與WAV只在ignored `.siro-data/verification/FIX005-ui-first24-20261017`。Uvicorn對故意abort的HTTP記錄 `gateway.py:811 CancelledError: speech client disconnected`；cleanup無錯，保留此log noise限制，不聲稱本輪沒有任何error log，也未證明它是新regression。

## 回歸與服務恢復

[cpu-regression.log](cpu-regression.log)：當前code **128 PASS / 2既有pypinyin warnings，6.98s**，未skip。涵蓋completion／error／cap、owned lifecycle／timeout／cancel／close、前端fetch取消、queue／預取與相容性。

```bash
.venv/bin/pytest -q tests/test_qwen_worker_completion.py tests/integration/test_qwen_lifecycle.py tests/integration/test_speech_completion_edges.py tests/integration/test_frontend_speech_cancel.py tests/integration/test_frontend_speech_queue.py
.venv/bin/python docs/evidence/FIX-005-first-segment-2026-10-16/verify_gpu_only.py --run-real --output .siro-data/verification/NEW-UNUSED-DIRECTORY
.venv/bin/python docs/evidence/FIX-005-first-segment-2026-10-17/serve_ui_probe.py --run-real --output .siro-data/verification/ANOTHER-UNUSED-DIRECTORY
```

後兩項需要先協調唯一GPU owner；UI server輸出origin後以CUA／實際滑鼠操作，結束送SIGTERM，不能同時執行兩個harness。各次新建目錄避免覆寫證據。harness compile、Ruff check／format及 `git diff --check` PASS。沒有production變更，因此未重跑上一輪2225項全套或雲端CI，不將舊結果冒充本輪。

finally完成後，沿原launcher恢復managed8000，`/health/ready` healthy；原控制台無草稿後reload，實際DOM「已連線」／control view／TTS待命。為恢復暫停期間已耗盡重連次數的native控制連線，graceful退出舊host後經原launcher重啟一次；仍單實例、alpha/sandbox=true、實際renderer owner=desktop，avatar-only診斷圖確認真Live2D。見 [restored-runtime.json](restored-runtime.json)。沒有另建Core/DB；正式設定仍是原模型與v1 reference，沒有複製測試cache進產品。

## 體驗限制與回退

首段工作量減少已在這兩個真機樣本看到較短等待，但仍約8–10秒，且冷載入約20秒。未達近即時接話；沒有真正逐音塊串流、LLM final前先播或保證後段無間隙。首段較短也可能暴露後段等待，必須分開檢驗。

人工音色／逐字語意／句尾由 owner 聽驗；原生桌寵滑鼠命中、多螢幕、走路／坐下素材、長期 soak 與部署 rollback 不在本次 GPU 對照的 PASS 範圍。本次沒有新的 production hunks可回退；上一輪 first24 修補的 source-only回退證據保留，不能覆寫目前 DB 或其他未提交工作。
