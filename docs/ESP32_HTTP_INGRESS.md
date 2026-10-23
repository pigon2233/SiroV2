# ESP32-S3 現有 HTTP 感測器接入 SIRO

目前實板沿用 `http://192.168.1.193:8765/event`，發送 `light_update`、`motion_detected`、`motion_cleared`、`button_pressed`。本接入沿用這個 ESP32 傳送格式，不需要 LED，也不使用尚未安裝的超音波感測器。

資料路徑：ESP32 → Windows 8765 接收器 → WSL 的 SIRO gateway loopback 入口 → 已註冊設備 → SIRO World State。Windows 接收器只轉送，不開啟第二個 SIRO 資料庫 writer。每筆資料只有在主程序驗證並寫入後才回覆 ESP32 HTTP 200；轉送 timeout 不自動重送。World State 的光度、PIR 動作與最近一次按鈕時間使用伺服器接收時間，20 秒後變成 unknown。`motion=false` 只表示未偵測到動作，**不代表房間無人**；這些 HTTP 事件不授權設備操作。

## 啟用前

1. 先確認 ESP32 的區網 IP。2026-10-23 15:20 的短暫現場觀察是 `192.168.1.182`；DHCP 可能改變，啟用當下要再核對。Windows 接收器要求 `SIRO_ESP32_ALLOWED_IP` 為**那台 ESP32**的 IPv4 位址；它不是電腦的 `192.168.1.193`。
2. 產生至少 32 字元的隨機 `SIRO_ESP32_RELAY_TOKEN`，在 Windows 接收器與 WSL SIRO gateway 使用相同值。將它放在各自的私人環境設定中，勿貼在聊天、記錄或 Git。Gateway 未設定時，入口回 503，不會建立設備 descriptor。
3. WSL gateway 設 `SIRO_ESP32_HTTP_DEVICE_ID=siro-node-01`（須與 ESP32 payload 的 `device` 相同），可選設 `SIRO_ESP32_HTTP_LOCATION`；已有同 ID 但不同 adapter 的設備會拒絕啟動，避免覆寫 MQTT 設備。
4. 用包含本變更的 SIRO 版本重新啟動主程序。**本地編譯／測試不會更新目前執行中的 8000 服務。** 先停掉原本的 `C:\Users\pepepig\siro_receiver.py`，再於 Windows 執行 `python scripts/esp32_http_receiver.py`；兩者不能同時占用 8765。

新接收器與原草稿同樣使用 `POST /event`、JSON、8765。它只接受設定的來源 IP；向 SIRO `127.0.0.1:8000/v1/devices/esp32/events` 轉送時帶獨立 relay token，不記錄原始 payload 或 token。這是區網 IP 限制加本機 relay 認證，**不是 ESP32 本身的雙向認證**。設備配對、憑證撤銷與 MQTT command／ack／readback 仍是 T27 正式驗收的獨立缺口。若要供自動化或發佈，須先完成這些安全條件與真人硬體測試。

核對順序：Windows `http://127.0.0.1:8000/health/live` 可達；接收器啟動後 ESP32 序列埠的 `light_update`、PIR 事件出現 HTTP 200；最後使用 SIRO 現有 `/v1/session` 取得 owner session token，讀 `GET /v1/devices/esp32/state`，確認 `illuminance`／`motion`／`last_button_press_at` 的 `status`、值、時間與 `device:siro-node-01:esp32_http` 來源。未有新事件或超過 20 秒時顯示 `unknown`，不回傳過期舊值。僅看到 HTTP 200 或舊接收器印出的 `SIRO EVENT`，不足以證明最後一步。本分支尚未安裝、啟動或刷入實板。
