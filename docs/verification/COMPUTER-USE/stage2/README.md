# 階段 2：固定集擴充與 Windows OCR 編號選點

本輪僅擴充階段 1 並實作階段 2，**未開始階段 3**。這是離線選點評測，不是實機遊玩成功率。

## 資料、標註及限制

- `cases.json`：**20 題、5 張不同的既存 STS2 畫面**，其中 15 題文字控制項、5 題無文字圖示。重複畫面的不同目標有相關性，不能說是 20 個獨立場景。
- 來源：本機 `siro-computer` 的 native-current、live-observation、learning-frame，加上 Pictures/Screenshots 的兩張 STS2 選單／戰鬥截圖。已查閱相關 repo、舊 worktree、trace/log 及截圖目錄；沒有找到可用的 2048／Notepad 保存畫面，不宣稱全機不存在。
- 每題均由 Grok Bot 逐張檢視並標註（未經使用者人工複核），記錄 `manual_visual_review`、情境、指令、框、SHA256、來源與不確定性；本輪 `uncertain=false`。只標註清楚可辨識的指定控制項，**不冒稱歷史操作成功，也不代表最佳遊戲策略**。沒有送出真實鍵鼠、沒有生成假截圖來湊數。
- 兩張高解析原圖固定縮為 1024 像素寬，來源尺寸／雜湊及 LANCZOS 轉換寫在 manifest；其餘保留原尺寸。模型前後使用同一凍結圖、指令、框及 manifest 雜湊。
- 遊戲圖保存在 `.siro-data/computer-bench-stage2/frames/`，沿用既有 gitignore，不提交原始截圖。`--image-root` 可指定內容相同的副本。
- `ocr/` 僅保存已檢視、只含遊戲 UI 文字的五份 OCR JSON，沒有截圖或私人對話；以影像 SHA256 命名。`ocr-inventory.json` 另記錄快取檔 SHA256。前後比較不讀取答案框來提示模型。
- 這也是 OCR 前處理的開發集，**不是獨立留出測試集**。只有一次完整量測、以選單為主，不能推論整體遊戲能力或統計顯著改善。

## 實作及安全邊界

- `ocr.py` + `windows_ocr_blocks.ps1`：WSL 傳既有圖的 JSON 到 Windows PowerShell，使用 **Windows.Media.Ocr**，沒有擷取螢幕／輸入／視窗 API。只使用已安裝的中文及 en-US 語言包，不下載安裝。
- pipeline 3：通用重疊水平帶、灰階對比與 2 倍放大；WinRT 文字框先依 `TextAngle` 繞帶中心順時針還原，再除比例、加裁切偏移，避免縮放／傾角造成錯點。沒有針對題目答案裁切或硬寫目標座標。
- 依穩定閱讀順序編號，重疊語言結果去重。模型只收到 **編號、OCR 文字、粗略方位**，不收到像素座標、正解框或原圖；只接受 ASCII 整數，0 表示無可辨識標籤。程式計算被選框中心；錯誤／未知 ID／OCR 失敗只等待，**不回退猜像素**。
- 既有 `decision.py` 只在工廠加一個可選 wrapper。`SIRO_COMPUTER_OCR_NUMBERED=1` 才啟用，預設 0；沒有變更任何持久環境設定。
- 純整數沒有語義信心分數，因此 **不捏造 confidence，保留 0 與既有低信心停機**；預設非自主 loop 會停下，不暗中開啟自主模式。實際執行仍受既有授權與安全機制限制，沒有進行真實輸入驗證。
- 安全閘、`SIRO_COMPUTER_ALLOWED_PROCESSES`、Ctrl+Alt+Shift+Esc、預設關閉原封不動。未修白名單、未改 loop、未批次動作。
- 既有 verifier 原樣保留；本輪只量決策，不宣稱整個 loop 都同樣加速。

## 評測與本機問題調查

- `SIRO_COMPUTER_BENCH_ENABLED=1` 才呼叫模型；編號評測還要 `SIRO_COMPUTER_OCR_NUMBERED=1` 與 `--ocr-cache`。雲端仍需既有 `SIRO_COMPUTER_CLOUD_SCREEN=1`，工具不自動代開。缺金鑰／服務記為未測，不寫成 0%。
- 每題一請求、不隱藏重試；等待、解析錯誤及錯點都不命中。五個無文字目標留在總分母，再另外分層列出。框含邊界，只算 left click。
- 秒數含 prompt／請求／解析，編號模式含讀取凍結 OCR 快取，**不含新畫面的 OCR、截圖、verify、settle 或輸入**。快取未命中 OCR 成本另列 `ocr-preparation.json`，並非整個操作 loop 延遲。
- `cold_seconds` 是本工具快取未命中的實測，不保證 Windows/WinRT 是系統第一次冷啟動；開發過程已啟動過 OCR。不得把相加推算冒稱實測端到端時間。
- Ollama 0.34.3 日誌確認 draft/MTP 載入有 `vector::_M_range_check`／HTTP 500；本輪僅 opt-in 單請求 `draft_num_predict=0`，所有 Ollama 推論 `num_ctx=8192`，未修改服務或停止其他負載。
- 不限 GPU 層的編號嘗試又出現 120 秒逾時；同時觀察到 GPU 7897/8192 MiB、100% 與 GPU discovery watchdog 使用過時可用記憶體。這是診斷線索，不把同時觀察當成唯一根因。讀取日誌後只中止自己的評測，沒有殺掉 Ollama 服務或使用者工作。
- 新增只用於 benchmark 的選項：`SIRO_COMPUTER_BENCH_NO_DRAFT=1`、`SIRO_COMPUTER_BENCH_GPU_LAYERS=24`；未設定則不覆寫對應選項。`SIRO_COMPUTER_BENCH_FAIL_FAST=1` 可在資源／連線逾時後停止該後端，預設不啟用。沒有持久設定變更。
- 24 層單題探測成功後，**Gemma 像素與編號都用相同 24 層條件**逐一評測 20 題，是否全數完成以原始結果為準，避免拿不同 GPU 配置或逾時冷啟動的舊數字冒稱公平加速。探測暖機不列入正式分母。最初無限制結果和中止紀錄僅作診斷。

## 重跑（僅 WSL）

```bash
cd /mnt/e/coding/股票策略機器學習/SiroV2
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sirov2"
CASES=docs/verification/COMPUTER-USE/stage2/cases.json
CACHE=docs/verification/COMPUTER-USE/stage2/ocr
uv run --no-sync python scripts/computer_click_eval.py "$CASES" --validate-only

# 已提交的快取可直接重現編號內容。重新 OCR 請用另一個空資料夾，別覆寫凍結證據。
uv run --no-sync python scripts/computer_click_eval.py "$CASES" \
  --prepare-ocr --ocr-cache .siro-data/computer-bench-stage2/ocr-new

# 請先確認已有 owner 雲端同意；要測本機可只選 --backend ollama。
SIRO_COMPUTER_BENCH_ENABLED=1 SIRO_COMPUTER_CLOUD_SCREEN=1 \
SIRO_COMPUTER_OCR_NUMBERED=1 SIRO_COMPUTER_BENCH_NO_DRAFT=1 \
SIRO_COMPUTER_BENCH_GPU_LAYERS=24 SIRO_COMPUTER_BENCH_FAIL_FAST=1 \
SIRO_COMPUTER_OLLAMA_MODEL=gemma4:e4b SIRO_OLLAMA_KEEP_ALIVE=15m \
uv run --no-sync python scripts/computer_click_eval.py "$CASES" \
  --mode numbered --ocr-cache "$CACHE" --backend all --timeout 120 --out /tmp/stage2-numbered.json
# 像素模式同條件只把 --mode 換成 pixel。
# --backend all 任一後端未測即 exit 2，仍完整保存成功後端，不代表工具崩潰。
```

參考：[WinRT TextAngle](https://learn.microsoft.com/en-us/uwp/api/windows.media.ocr.ocrresult.textangle)、[Microsoft OCR sample](https://github.com/microsoft/Windows-universal-samples/blob/main/Samples/OCR/cs/OcrFileImage.xaml.cs)、[Ollama draft 停用建議](https://github.com/ollama/ollama/issues/18517)。
## 本輪結果（2026-11-10，Asia/Taipei）

下表均為完整 20 題；Gemma 兩模式都使用 GPU 24 層、draft 關閉、context=8192，先完成單題資源探測暖機，再按像素→編號順序執行。CLI/API 與服務快取狀態沒有額外清空。原始來源與精確值見 `comparison.json`。

| 後端／模式 | 總命中 | 平均秒／步 | 中位秒／步 | 文字 15 題 | 無文字 5 題 |
|---|---:|---:|---:|---:|---:|
| Claude 像素 | 20/20（100%） | 6.001 | 5.512 | 15/15 | 5/5 |
| Claude 編號 | 11/20（55%） | 4.212 | 4.143 | 11/15 | 0/5 |
| Gemma 像素（24 層） | 0/20（0%） | 15.877 | 15.192 | 0/15 | 0/5 |
| Gemma 編號（24 層） | 12/20（60%） | 1.291 | 1.371 | 12/15 | 0/5 |
| Groq（兩模式） | 未測 | — | — | — | — |

- **改善：本機 Gemma 編號決策 1.29 秒、12/20 命中；像素版 0/20，另有 8 題解析失敗。** 編號版沒有解析失敗。
- **代價：Claude 準確率退步（100%→55%），不能宣稱 OCR 全面優於視覺模型，維持預設關閉。** Claude 編號一題選錯區塊，其餘未命中均等待；Gemma 編號未命中均等待。
- 兩種編號模式的 **5 個無文字圖示全部未命中**，沒有從分母移除。文字題命中 Claude 11/15（73.3%）、Gemma 12/15（80%）。
- OCR 中心可覆蓋 13/20 個目標；有文字但未產生可用框的是右側 Defend 卡與事件 Continue。戰鬥 End Turn 雖有框，文字被辨成錯字，兩模型均等待。仍需改善卡牌／圖示及 OCR 覆蓋，不能把未讀到文字重新標成「無文字」來美化分數。
- 表中編號模式使用**凍結 OCR 快取**。五張不同圖未命中本工具快取的實測 OCR：平均 **0.896 秒**、中位 **0.589 秒**；不含在表內，也不是系統首次 WinRT 冷啟動的保證。
- Groq 本輪 WSL 環境沒有 `SIRO_OPENAI_API_KEY`，沒有詢問、讀取私密金鑰檔或編造數值。
- 最早自動 GPU 配置的像素結果是 0/20、平均 13.530／中位 8.016 秒（含一題 120 秒逾時及其他解析錯誤），保留於 `gemma-pixel.json` 作診斷，不混入匹配 24 層主比較。中止的初次編號紀錄及前置探測失敗也保留。

## 驗證與交付邊界

- 新模式測試 **52 passed**；加既有離線評測契約合計 **80 passed**。
- computer-use unit/integration 回歸 **290 passed、4 failed**。四個皆是階段 1 已記錄的既有 `test_computer_use_perception.py` 失敗：screen.png fixture、claude_failed、missing_expect、history `saw:`／`saw=` 不合；沒有刪測試或放寬門檻，並非全套通過。
- 本任務四個 Python 檔 Ruff check、format check、mypy 通過，凍結 manifest 驗證通過；完整命令及 stdout/stderr 見 `tests.json`。
- 新測試實際驗證 strict ID、座標轉換／傾角、影像快取身份／版本／邊界、雲端同意、預設關閉、無輸入執行、既有低信心閘、取消及資源逾時快停。
- 驗證中修正了 fixture 時鐘、production 包裝後的小寫 timeout 代碼，以及把語義未驗證誤標成「畫面不可讀」的欄位；仍維持 `confidence=0`，沒有改模型提示詞、金標框或選點座標。這些不影響既有離線量測的 click 判定。
- 交付為 **LOCAL_ONLY / NOT PUSHED；驗證 PARTIAL**（既有四個回歸失敗、Groq 未測、覆蓋有限、沒有實機鍵鼠驗證）。安全閘與白名單等不變。不進入階段 3。