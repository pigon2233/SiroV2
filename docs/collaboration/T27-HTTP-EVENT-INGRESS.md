# T27 ESP32 HTTP 事件轉 SIRO 狀態：本機交接

- Owner：Codex；2026-10-23 Asia/Taipei；**LOCAL_ONLY／BLOCKED_SYNC**。修改前查詢 GitHub 未結 Issue／PR 為空，`origin/main` 為 `89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；先前 GitHub 寫入憑證不可用，故尚未線上認領。恢復認證後須重查競爭認領。
- Base：本機 `codex/t27-esp32-sensor-telemetry`@`a5f79e5`（該分支尚未推送）；本分支 `codex/t27-http-event-ingress`、獨立 worktree `E:/coding/Worktrees/t27-http-event-ingress/SiroV2`。與先前 T27 感測韌體變更有前置依賴。
- 範圍：只在 `src/siro/services/devices/http_sensor.py` 建立使用者現有 HTTP `light_update`、`motion_detected`、`motion_cleared`、`button_pressed` 的嚴格 parser 與 World State 投影元件，測試在 `tests/integration/test_esp32_http_sensor.py`；保留 `C:/Users/pepepig/siro_receiver.py` 原檔與原服務。
- 契約界線：不新增正式 HTTP route、不讓外部程序寫 SIRO 主資料庫、不賦予事件設備控制權。正式接入 `/event` 涉及入口認證與路由契約，待 `docs/DECISIONS.md` 與受影響測試由共享文件 owner 審核後實作；這份文件不是決策紀錄或共享鎖。
- 驗收：合成 payload 經 parser、Registry、SQLite World 觀測；拒絕格式錯誤、偽造 device、異常 lux；驗證時間與失效、PIR 低電平不推斷房間無人。實板 POST 仍由使用者舊接收器單獨接收，不宣稱 SIRO 已線上感知。
- 結果：20 項相關測試 PASS／4.81s；Ruff check／format、mypy、diff PASS。詳見 [本輪證據](../evidence/T27-http-event-projector-2026-10-23/REPORT.md)。沒有 live ingress 或實板驗收。
