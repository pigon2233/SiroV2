# COMPUTER-CONTROL-CONTINUATION-20261110

## 交接狀態

PARTIAL（模型品質未達全部目標；C/D 工程驗收完成）／LOCAL_ONLY／NOT PUSHED。
Owner：Grok Bot；使用者 pt9u 授權 A→B→C→D 連續完成；2026-11-10～11（Asia/Taipei）。
工作區：E:\coding\股票策略機器學習\SiroV2，本機 main；依使用者明確要求覆蓋預設 worktree 流程。
基線：e9e723d78a2555ab03f374c06e43aeb1348c7ecc。遠端認領 UNKNOWN，未宣稱跨機鎖定；未推送、未發布、未部署。
僅修改本任務檔案；未改共享 STATUS/DECISIONS、鎖檔、使用者設定或執行中服務。
沒有真實點按／按鍵／現場擷取；純測試中的輸入全為假橋接。不能宣稱真遊戲控制已完全正常。

## 分步提交與檔案

- A：2fc4daf9d70e6209732bb0da3276eee0a76b2527
  - 新增 computer_use/{regions,hybrid}.py，修改 numbered.py、scripts/computer_click_eval.py。
  - tests/unit/test_computer_use_hybrid.py；continuation/step-a/**（所有迭代與失敗皆保留）、.gitattributes、本交接。
  - OCR 優先；明確回 0 才轉通用輪廓／色塊編號；再回 0 才允許另旗標的像素 fallback。錯誤輸出封閉失敗。
  - REGION_NUMBERED、REGION_PIXEL_FALLBACK、REGION_GALLERY 都在 SIRO_COMPUTER_ 前綴下，皆預設 0；gallery 實測較差，不推薦。
- B／階段3：f498e7fe9a9db3cdd015baf4285b60b150435a91
  - 新增 batch.py、batch_decision.py；修改 decision.py、hybrid.py、loop.py。
  - scripts/computer_batch_eval.py、test_computer_use_batch.py、continuation/step-b/**。
  - SIRO_COMPUTER_ACTION_BATCH=1 且 SIRO_COMPUTER_BATCH_PROCESSES 額外子白名單非空才有作用；預設停用。
  - 僅回合制 combat、2～4 個不同左鍵目標；每次輸入仍檢查新鮮觀察、同 HWND/PID/幾何、隱私、像素 guard、急停世代與既有 gate；只有語意驗證延至最後。
  - 未知結果、限流、部分失敗立即停止，不重送。最後未確認／未見變化不能當成功。
- C／階段4：c41aa4ad8c50406dbf92edb91706b578ed231c23
  - 新增 interface.py、observe.py、decide.py、execute.py、verify.py、stuck.py；修改 loop.py、decision.py。
  - test_computer_use_modules.py、continuation/step-c/**。
  - 單一 Decider/Decision/VerifyResult 介面；保留舊 import、公開 API、可選後端及 loop 的動態 timing 常數。
  - 13 個抽出的純函式 AST 不變，3 個舊 provider prompt 值不變；此為保行為拆分，沒有新增執行模式。
- D／階段5：本文件同一提交（完整 SHA 見最終回報；可用 git log -1 --format=%H -- 本檔查詢）。
  - 新增 process_names.py；必要修改 perception.py、bridge.py、intent.py、loop.py、observe.py、batch.py、batch_decision.py。
  - desktop-win/{computer-control.js,computer-bridge.js,input-helper.ps1,process-names.ps1,process-names.test.js,process-names.test.ps1}。
  - tests/fixtures/computer-process-names.json、test_computer_process_names.py。
  - SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES 預設 0；開啟才忽略大小寫／空白／標點，僅精確正規化相等，不做 prefix/substring/title 授權。
  - 原生聚焦同時修正；多個候選有歧義就拒絕。拒絕空名稱、路徑、不同數字與 helper 尾碼；保留嵌入的 .exe，避免剝除兩次而擴張匹配。
  - 隱私黑名單同步正規化，不能用空白／標點繞過。HWND/PID/rect fence 保持原樣。
  - 評測器新增輸出父目錄建立／先印完整報告，補 test_computer_click_eval.py，修正一次模型已跑完但檔案存不下的錯誤。
  - continuation/step-d/**、comparison-final.json 與本交接。

## 固定資料與數字

20 個任務，只來自 5 張真正獨立 STS2 存檔畫面（15 文字、5 無文字圖示）。
來源：先前保存的 siro-computer 三張畫面與 Pictures/Screenshots 兩張選單／戰鬥畫面；標籤皆人工看圖、記錄來源，不是已驗證成功動作或最佳策略。
沒有可用的新 2048／Notepad 已存畫面；未以真輸入製造新資料。這是反覆調整使用的 development set，非 held-out；不能以 20 案當 20 種獨立場景。
manifest SHA256：914077f0196b22cb93dc08413668656f478e7066c097a683c740ec46c350a00a。
原圖仍私有／gitignored；OCR 依原圖 SHA256 固定快取，所有模式相同分母，無字目標未排除。

| Backend / mode | All hits | Mean / median sec | No-text hits | No-text mean / median sec |
|---|---:|---:|---:|---:|
|Claude pixel (final)|20/20|5.59 / 5.39|5/5|5.79 / 5.42|
|Claude OCR IDs (Stage2)|11/20|4.21 / 4.14|0/5|4.16 / 4.18|
|Claude hybrid (A final)|17/20|4.54 / 2.76|3/5|8.12 / 7.73|
|Gemma pixel GPU24 (final)|0/20|14.32 / 14.71|0/5|12.65 / 12.47|
|Gemma OCR IDs GPU24 (Stage2)|12/20|1.29 / 1.37|0/5|1.31 / 1.35|
|Gemma hybrid GPU24 (A final)|17/20|2.30 / 0.70|4/5|4.64 / 4.29|


完整機讀來源在 comparison-final.json。OCR IDs 是既有階段2數據；pixel 是本輪重測；hybrid 是 A 最終版，不挑先前較好的單輪。
時間含請求／解析／hybrid 路由，使用固定 OCR 快取；不含現場擷取、冷 OCR、遊戲等待、驗證與輸入，不能當真遊戲每步耗時。
冷 OCR 成本另見階段2報告。Gemma 全部 num_ctx=8192；GPU24、draft_num_predict=0、keep_alive=15m 避開先前 MTP/GPU 記憶體問題，未重啟或改全域服務。
Gemma pixel 的 12 個非 JSON 錯誤都算未命中；Claude hybrid 的 1 個無效編號也算未命中，沒有盲重試。
Groq：呼叫環境沒有既有 key，未測，未抽取任何憑證或要求使用者提供。

A 有通用候選中心覆蓋20/20，但最終模型只17/20，尚未達 >=18/20。Claude 早期 v1 曾18/20，不能冒充目前結果；所有迭代與 v4 簽名錯誤均保留。
Gemma 尚錯 End Turn／Defend／地圖，Claude 尚有多人模式／地圖／無效編號問題。不可宣稱 hybrid 嚴格優於 Claude pixel。
B 僅各1次兩目標定位探測：Gemma8.960秒（回3動作，前2目標皆錯）、Claude8.347秒（1/2正確），均未兩目標全中；不是成功遊戲序列，不宣稱 batch 加速或勝率。

## 最終測試

全部 Python 測試／評測在 WSL，UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2；未在 Windows checkout 執行 uv run。
- 定向單元／評測器：97 passed（包含新增純安全契約與輸出目錄回歸）。
- 完整 computer-use：359 passed /4 既有 failures；名稱旗標 OFF 與 ON 都相同，無新增失敗。
- 既有失敗未刪除／跳過／放寬：screen.png vs screen.jpg fixture、CLI transient retry expectation、missing_expect fixture、saw: vs saw=。
- Ruff：本次變更範圍通過；mypy --follow-imports=silent：24檔通過，非全專案型別檢查。
- Node 假桌面回歸32/32；原生 PowerShell19共享向量、歧義／雙副檔名邊界、input-helper語法檢查通過。未執行原生 input helper 或真輸入。
- checks.json 保存命令／真實 exit code；4舊失敗的 pytest exit仍為1，沒有偽裝成全綠。
- safety.py 與桌面 main.js 的 Ctrl+Alt+Shift+Esc 完全未改；主白名單內容、預設關閉與安全閘未弱化。

## 建議實玩設定（沒有替使用者套用）

優先可靠性：仍用 Claude pixel，另啟用精確名稱匹配與畫面 guard。
```dotenv
SIRO_COMPUTER_DECIDER=claude
SIRO_COMPUTER_CLOUD_SCREEN=1
SIRO_COMPUTER_ALLOWED_PROCESSES=slaythespire2.exe
SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES=1
SIRO_COMPUTER_SCREEN_GUARD=1
SIRO_COMPUTER_OCR_NUMBERED=0
SIRO_COMPUTER_REGION_NUMBERED=0
SIRO_COMPUTER_REGION_PIXEL_FALLBACK=0
SIRO_COMPUTER_REGION_GALLERY=0
SIRO_COMPUTER_ACTION_BATCH=0
SIRO_COMPUTER_CONTROL_ENABLED=0
```
CLOUD_SCREEN=1 僅適用主人同意傳遊戲畫面；控制維持預設關閉，真正遊玩仍由主人在既有托盤介面明確開啟，急停熱鍵不變。
沒有自動改設定、重啟或部署；後端與桌面需要正常重新載入才會採用新程式。
本機 hybrid 如另行實驗：gemma4:e4b、SIRO_COMPUTER_OLLAMA_NO_DRAFT=1、SIRO_COMPUTER_OLLAMA_GPU_LAYERS=24，保留所有安全限制。
純編號沒有模型語意 confidence，保留0與原 low_confidence停機；不能為了展示可動而虛造高信心或建議繞過該停止。

## 還缺什麼／回退

需要更多獨立 hold-out 遊戲畫面、可靠視覺選擇／語意信心、成功批次的時間序列標籤與另外授權的真遊戲驗證，才能宣稱控制沒有問題。
目前不推薦把 hybrid／batch 當正式預設；不再新增其他階段。關閉各新旗標可回到舊路徑；不做 reset/clean 或動使用者服務。
交付後僅本機提交，無 push；最終 SHA／工作區狀態見回報。