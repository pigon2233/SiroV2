# E 槽 WSL 本機補齊與啟動驗收 — 2026-10-17

依使用者「幫我補好／繼續」，補齊此台 Windows 的本機模型、合法 Live2D 素材、桌寵依賴與啟動入口。使用者在本聊天明確同意 Cubism Web 5-r.5 與 Haru 的官方條款。這是本機接續設定，並非全專案完成、正式 signed release、remote CI 或 L3 硬體認證。

## 已完成的本機入口

實際執行根目錄 `Start-SIRO.cmd`，經 Ubuntu `~/.local/bin/siro-companion` 啟動已核對的執行副本；`http://127.0.0.1:8000/health/ready` 為 healthy，唯一所選 gjs host 存活。桌寵與正式後端留給使用者操作。開始選單另有「SIRO 桌寵」，Exec 指向同一 wrapper；已安裝並核對內容，沒有人工點擊選單驗收。

- Windows source 保留在 E 槽；Ubuntu distro 位於 `E:\WSL\Ubuntu`，副本／venv／cache／models／assets／資料也在此 VHD。
- 最終執行副本 ID 前綴 `8fb7636d6e98`，完整識別、實際命令與結果見 [RESULTS.json](RESULTS.json)。副本的 142 個 src 檔完整，複製前／副本／來源複製後三方 hash 相符，專用 editable import／Python prefix 相符，原共享 venv 沒有被改指向。
- Wrapper 的執行環境、模型及資產位置記在 `~/.local/share/siro/local-runtime.json`。資料與 logs 分別是 `~/.local/share/siro/data`、`logs`；source 內沒有產生 `.siro-data`。之後 Windows 修改不會自動部署。
- Ollama 0.34.3 user service 只綁 `127.0.0.1:11434`，`OLLAMA_NO_CLOUD=1`；選官方 `qwen3:4b-instruct` Q4_K_M，4096 context。無 API key、雲端語音或付費服務設定。此 profile 明確選既有 byte-budget mode；預設 native token guard 與驗收上限保持。

## 修正範圍與環境

Windows CRLF 使 scripts 無法執行：補 `.gitattributes` 的 LF 規則並正規化腳本，沒有重寫其他使用者變更。桌寵入口改以已選 uv 環境執行；選單保留明確的非 secret 執行路徑、模型及 0/1 budget 設定，正確處理 Desktop Entry 轉義。`start-companion` 尊重外置 data/log 路徑。

DrvFS 的 gateway import 曾量到 17.265 秒，DB 初始化 0.390 秒；未以此證明每次 cold latency。採已 provision 的 ext4 執行副本與專用 Python cache，未改 SQL、放寬原 5 秒測試或使用 `/tmp` 冒充 ext4。`/tmp` 實際是 tmpfs。Python 選 3.12.14，因原 lock 的 Kokoro／Misaki metadata 不支援 3.14，Python／Cargo lock 不變。

已安裝 GJS 1.88、GTK 3.24.52、WebKitGTK 2.52.6（GI API 4.1）、中文字型與 emoji 字型；沒有關閉 WebKit sandbox、修改全域 AppArmor 或安裝 Electron。Rust 1.97.1、uv 0.12.18、Node 22.22.1 可用，WSL 可見 RTX 3050 8GB。

真 QA 發現原 `qwen3:4b` 將 512 output 用完仍只有推理，且 Ollama adapter 把 length／缺 terminal 誤當 finished。保留原模型，選 instruct 並修唯一 adapter 葉節點；重用 FIX-003 的 truncated／incomplete，partial 文字保留，取消優先，工具完整終止並 cleanup 後才釋出。Core、Policy、schema、512 上限與重試政策不變。D63 先記決策、新測試 RED 後修；舊 protocol 測試只調整已審核的一處工具 chunk 預期，原安全錯誤／零 fallback／close 斷言保留。獨立唯讀 review 無具體 blocker。

## 實跑證據

| 類型 | 命令或流程 | 實際結果 |
|---|---|---|
| 合成回歸／真本機程序 | `check_ext4.py`，9 個啟動／桌面／限流／語音計畫檔與7個模型相關檔 | **261 PASS，1 既有 Starlette warning，17.34s，exit0**；包含未改的5秒啟動測試 |
| Adapter 合成回退 | 原 adapter bytes 注入新37例 | **31 FAIL／6 PASS**；修後37 PASS；原工具斷言兩反例 baseline 2 FAIL／2 PASS |
| Adapter 相鄰回歸 | `ollama_check.py regression-final` | **177 PASS／17.28s／exit0**；Ruff check／format／mypy三檔通過 |
| 桌面腳本回歸 | 新 installer 測試及原桌面兩組 | **51 PASS／10.76s**；Ruff／format／mypy／Bash syntax通過 |
| 真 build | 新副本 locked uv sync／compileall／Cargo build | exit0；較早本輪 Rust24 PASS，最終副本只重 build，不將其記為再跑24例 |
| 真模型 API | instruct，合成短問候，num_predict128 | 6.231s、3 tokens、「您好！」、done stop、thinking0；只證單次樣本 |
| 真產品整合 | `verify_integrated.py`，正式 `scripts/start`、臨時合成 DB、Chromium、Ollama、Haru、GJS | **PASS**；ready0.913s、回覆「你好呀！😊」、completed、工具效果0、page errors0 |
| 真原生 renderer | 同一整合；web釋放後啟動GJS | Haru canvas1、F01；ready／alpha／sandbox均true，snapshots3、input regions42；native exit0／closedtrue |
| 真清理 | 同一整合 | stop exit0、backend143、PID清、source無私有目錄；無cleanup errors |
| 正式 Windows 入口 | `Start-SIRO.cmd`＋`check_final_entry.py` | healthy、模型／TTS路由正確、唯一gjs、doctor gateway available；**留在執行中** |
| 真本機 TTS | 既有 KokoroLocalTTS，合成中文，Python網路audit guard | 24kHz、2.432s、有限非零WAV116780bytes；cold4.7425s、連線嘗試0；非真人聽驗 |

WSL helper 保留在本機 ignored `.siro-data/wsl-setup/`。主要可重跑命令（從 Windows source 目錄）：

```powershell
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_ext4.py
wsl -d Ubuntu -- env SIRO_OLLAMA_MODEL=qwen3:4b-instruct bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/verify_integrated.py
wsl -d Ubuntu -- bash -lc '~/.local/bin/siro-companion --doctor --json'
.\Start-SIRO.cmd
wsl -d Ubuntu -- bash .siro-data/wsl-setup/run.sh python .siro-data/wsl-setup/check_final_entry.py
```

`refresh_ext4.py` 會建立新副本；只有 source 已穩定、準備重新部署時才執行。完整機器本地 manifest／命令／log 分別在該 snapshot 的 sibling `metadata` 及 ignored setup 目錄。此副本只帶本次相關測試 closure，不能拿來宣稱完整 `scripts/check` 已通過。

## 來源、授權與供應鏈

- [Ollama 0.34.3 官方 release](https://github.com/ollama/ollama/releases/tag/v0.34.3)：MIT。Linux amd64 zstd archive 驗 SHA 後解包；[Qwen3 instruct 官方模型](https://ollama.com/library/qwen3:4b-instruct)：Apache-2.0。本機完整 digest 記在 RESULTS；原4b安裝保持。
- [Live2D 官方下載／條款](https://www.live2d.com/en/sdk/download/web/)：Cubism Web 5-r.5 archive SHA 與 repo pin 相符。用既有 prepare／repair scripts 建出單Haru renderer，接受紀錄與manifest保留在本機，Core／Haru／archive不進Git。
- 外置 SDK 的 npm 初始7個 build-only漏洞，採相容 `npm audit fix --ignore-scripts`，package manifest及renderer source hash不變；最終 **audit0／build exit0**。外置 `package-lock.json` 已更新，版本與lock摘要記於 RESULTS；未改專案 Python／Cargo lock。
- [Kokoro 官方模型](https://huggingface.co/hexgrad/Kokoro-82M)、[固定 ONNX 轉換來源](https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/tree/1939ad2a8e416c0acfeecc08a694d14ef25f2231)、[voices release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)：weights Apache-2.0／SDK MIT。本機 runtime q4 檔名是明確別名，來源與完整SHA記在 assets manifest；沒有把相似檔名當官方原檔。

## 保留的早期失敗與限制

原 CRLF／5秒失敗保留在 [WSL-RUN report](../WSL-RUN-2026-10-17/REPORT.md)。第一輪整合用 `/mnt/e` 診斷目錄，GLib atomic chmod EPERM而無法更新native狀態；第二輪native已ready，但copytree的metadata複製EPERM造成harness清理流程未完成。兩輪檔案保留為 ignored `integrated-first-run`／`integrated-prior-*`。只修QA路徑與逐bytes複製／nested finally／checkpoint；第二輪精確argv、environ、FD掃描均無owned程序命中，沒有廣殺其他service。最後完整重跑PASS不掩蓋前兩輪。

Native有MESA／EGL warning，但真畫面／透明／sandbox檢查通過；不保證GPU硬體合成或其他機器／OS。正式入口檢查最初誤假設host使用絕對argv路徑，唯讀確認為`gjs -m desktop/host.js`後改核對精確argv＋snapshot cwd；沒有以此改產品。

原個人Qwen reference聲線缺少，未恢復。現用本機Kokoro備用聲音；真人揚聲器／麥克風／語意與長文品質、首音SLO、24h soak未驗。取消awaitable能返回CancelledError且不回傳音訊，但原asyncio.to_thread不能中斷已進入的ONNX native worker，實測另5.6454s後join；不能宣稱原生推論立即停止。

語音辨識尚無provider設定，audio route為disabled，先打字使用。現有minimal doctor的config（舊`~/.config/siro/config.json`）、wpctl與Docker顯示unavailable；此入口使用已核對的wrapper環境，並非那個config檔。沒有Docker容器broker或Linux系統音控驗收，未為了變綠建立假設定。Haru現有骨架不代表步行／坐下／自由漫遊已完成。其餘產品智慧、語音、搜尋、自治、硬體與正式發布gates均保持。

下一步：使用者實際試打字、角色操作與備用聲音；依既有T12／桌面體驗卡驗交互，再分別配置語音辨識及原聲線、執行真人音訊驗收。不再把新機安裝等同整個SIRO交付完成。
