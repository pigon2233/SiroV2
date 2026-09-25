# SIRO 2 初始部署政策

版本：1｜任務：T00。這是沒有使用者敏感資料偏好時的保守預設；後續 Setup UI 讓使用者明確修改。設定值將在 T01 建立 versioned schema。

## 平台與 profile

- 第一實測平台：Ubuntu 26.04、x86_64、Wayland/GNOME。
- 預設 profile：`minimal`，只啟用 CLI/Core、mock model、本地資料。
- Companion/local-ai/distributed 均需對應 task gate，不因偵測到硬體就自動啟用。
- Windows 是規劃目標，尚未有實測主機，不標示 supported。

## 資料與外送預設

- 全部資料初始 `local_only`；cloud provider routes 關閉。
- 原始音訊/影像只在記憶體短暫處理，不持久保存。
- 對話與記憶預設寫本地資料目錄；T17 前只有為測試建立的合成資料。
- operational logs 預設不記 prompt/response/secret，保留 14 天是後續產品預設；T01 只實作 redaction 基線。
- telemetry 不外送；之後若加入，必須 opt-in 並列出欄位與目的地。
- 任何 provider 外送需要明確配置目的地、資料類別、每次/每日成本上限；未配置即拒絕。

## Secret 與資料目錄

- Git 中只允許 `.env.example` 的變數名稱，不允許真值。
- T01 不要求任何 API key；`siro doctor` 只回報能力 unavailable。
- runtime data 遵循 XDG，預設 `$XDG_DATA_HOME/siro` 或使用者資料目錄；cache/config 分開。測試一律使用 pytest temporary directory。
- 正式 secret store 在 T07/T21 前另做 ADR；禁止把 token 放進一般 YAML/JSON、URL query、log 或 evidence。

## Backup 與 retention

- T04 前沒有 production DB；備份功能尚未存在。
- T04 建立一致性 backup 基礎，T34 才提供正式操作入口。
- 正式備份預設由使用者主動執行、排除 secret，輸出 manifest/hash；加密預設需要使用者選定 key management 後才可聲稱完成。
- 未設定加密時不可自動把備份放到 cloud/shared folder。
- Memory 刪除、衍生索引及舊備份的生命週期依 SECURITY_PRIVACY 執行。

## 網路與控制

- HTTP/WS 預設只綁 loopback；LAN/remote disabled。
- Runtime、device、compute 寫入能力在對應任務完成 grant/pairing 前全部 disabled。
- 主動聊天預設 disabled；quiet hours 初值 23:00–08:00 Asia/Taipei，只有使用者啟用後生效。
- 第三方 skills 初始 disabled；模型不能自行打開。
- NVIDIA、相機、Docker 不可用時採 degraded/unavailable，不自動安裝 driver、改 group 或擴權。

## T00 決策結果

可以立即開始 T01–T08 的 minimal profile。GPU、cloud、Live2D、音訊、設備、Windows 與 distributed 能力各自在任務 gate 驗證。這些外部條件不阻塞骨架、契約、Event Bus、SQLite 和文字核心。
