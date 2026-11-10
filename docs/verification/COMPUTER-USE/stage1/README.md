# 階段 1：固定截圖點擊基準 v1

## 範圍與標註

- `cases.json` 固定 **3 張不重複的既存 STS2 原始截圖**：主選單繼續、對話繼續、戰鬥結束回合。
- 來源：本機 `siro-computer/{native-current.jpg,live-observation.jpg,learning-frame.png}`。Grok Bot 已逐張看圖，人工標註可辨識控制項；每筆保留 `label_source`、情境、明確指令、原圖尺寸、SHA256 與 `uncertain`。
- 本輪均屬清楚的控制項定位標註，`uncertain=false`；**不是最佳遊戲策略，也沒有冒稱歷史動作成功**。戰鬥題明確要求結束回合，即使仍有能量。
- 影像副本固定於 repo 的 `.siro-data/computer-bench-stage1/frames/`，已由既有規則忽略，不提交遊戲畫面。可用 `--image-root` 指定另一份相同雜湊的副本；不能繼續引用會被覆寫的 current 圖。
- 座標為原截圖像素、`[x0,y0,x1,y1]`，四邊含邊界。只有 `act + left click` 且落入框內算命中；移動、右鍵、按鍵、等待或解析錯誤不算命中。
- `uncertain=true` 題目會列出但排除，不會偷偷當成正確。影像雜湊、尺寸、框、標註來源與 ID 先驗證，失敗不呼叫模型。
- 去掉重複 learning-frame、桌面畫面、已有 OCR/編號/atlas 的衍生圖，避免把階段 2 提示混入階段 1。
- 檢查了 repo、相關 computer worktree 與本機 siro-computer 素材；未找到可用的既存 2048／Notepad 截圖。此處不宣稱全機不存在。**3 題只能當定位 smoke baseline，不能推論普遍遊戲能力**；每題即 33.3 個百分點，沒有統計顯著性主張。

## 安全與計時邊界

獨立工具 `scripts/computer_click_eval.py`，不修改或啟動 runtime，不建構 bridge／loop、不擷取畫面、不驗證實機、不送鍵鼠。安全閘、`SIRO_COMPUTER_ALLOWED_PROCESSES`、Ctrl+Alt+Shift+Esc、預設關閉均原封不動。

- 新離線模型呼叫預設關閉：`SIRO_COMPUTER_BENCH_ENABLED=1` 才可跑；`--validate-only` 無須開啟。
- 雲端仍需要既有 `SIRO_COMPUTER_CLOUD_SCREEN=1`；工具不會自動開。僅選定的遊戲裁切截圖送給所選雲端提供者，不載入聊天或記憶。未配置 API key、CLI 或服務時明列 `not_measured`，不是 0% 命中。
- 重用三種既有決策器的 `_decide_once`，使用相同 production prompt、座標網格及 parser；**每題一次請求，沒有隱藏重試**。指令不包含正解框或標註。
- 計時用 monotonic `perf_counter`：包含 prompt/座標網格、請求、解析；不含讀圖、前置服務探測、截圖、驗證、等待或真正輸入，因此不是整個操作 loop 的總耗時。第一題含模型冷啟動／快取狀態，不額外暖機。
- Ollama 僅在評測 client 的 transport 將 `num_ctx` 設 **8192**，不更改 runtime 既有值或其他選項。模型、網格設定、每題輸出、耗時、錯誤、平均與中位數寫入報告。
- 若有有效輸出但某題解析失敗，該題計 miss，耗時也計入平均並列 errors；整個後端完全沒有有效輸出則不列命中率與平均。缺授權立即停止該後端。
- `--backend all` 有任一後端未測，保留完整報告並 exit 2；這不是測試工具崩潰或全部後端 0%。

## 重跑（WSL）

在 `/mnt/e/coding/股票策略機器學習/SiroV2`：

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sirov2"
uv run --no-sync python scripts/computer_click_eval.py \
  docs/verification/COMPUTER-USE/stage1/cases.json --validate-only

# 純本機，不外送
SIRO_COMPUTER_BENCH_ENABLED=1 SIRO_COMPUTER_OLLAMA_MODEL=gemma4:e4b \
  uv run --no-sync python scripts/computer_click_eval.py \
  docs/verification/COMPUTER-USE/stage1/cases.json --backend ollama --out /tmp/stage1-local.json

# 已獲 owner 同意雲端評測時；API key 只由呼叫環境提供，不讀 token/credential 檔
SIRO_COMPUTER_BENCH_ENABLED=1 SIRO_COMPUTER_CLOUD_SCREEN=1 \
  SIRO_COMPUTER_OLLAMA_MODEL=gemma4:e4b \
  uv run --no-sync python scripts/computer_click_eval.py \
  docs/verification/COMPUTER-USE/stage1/cases.json --backend all --out /tmp/stage1-all.json
```

`baseline.json` 是本輪原始量測，時間為 Asia/Taipei。不要拿舊計畫「Claude 7–10 秒」當本輪結果。下一階段若獲准，使用同一 manifest 與尺寸／框比較；本輪未實作 OCR、批次動作、拆檔或白名單修正。

## 本輪結果（2026-11-10，Asia/Taipei）

| 後端 | 命中率 | 平均秒／步 | 中位秒／步 | 備註 |
|---|---:|---:|---:|---|
| Claude `claude-haiku-5-5` | 3/3（100%） | 6.026 | 5.873 | 單次 production 決策請求 |
| Ollama `gemma4:e4b` | 未量得 | — | — | 3 題均在 90 秒逾時（原始實際等待約 90.094 秒）；不是 0% 正常完成 |
| Groq `qwen/qwen3.8-27b` | 未測 | — | — | 呼叫環境沒有 SIRO_OPENAI_API_KEY；沒有讀取金鑰檔取得它 |

Ollama 探測可列到模型，`/api/ps` 確認 context=8192；逾時期間 GPU 快照 7744/8192 MiB、利用率 100%。這只是同時觀察，不能據此斷言根因。沒有重啟服務、停止既有負載或盲目重試相同題目。

驗證：新測試 **28 passed**；Ruff check／format 與兩個新 Python 檔 mypy 通過。全部 computer 相關 Python 回歸 **238 passed、4 failed**。四個失敗都在既有 `test_computer_use_perception.py`；獨立只跑該舊檔仍 **27 passed、4 failed**，且相關既有程式／測試與 HEAD 無差異。錯誤分別為舊 fixture 的 screen.png、claude_failed、missing_expect、history 字串格式不合；本階段沒有改它們或放寬驗收。詳見 `tests.json`。

交付狀態：**工具與小型固定集完成，跨後端量測 PARTIAL**；截圖覆蓋不足、本機逾時與 Groq 設定缺口皆保留為限制。等待 owner 決定後續；不進入階段 2。
