# T27 ESP32 HTTP 光度與 PIR 現場驗收

日期：2026-10-18。結果：**PARTIAL**。本報告只涵蓋現有 HTTP 感測器上報鏈路；T27 MQTT 與 A18 L3 閉環維持既有狀態。

## 已知格式與現場回報

使用者提供的 ESP32 草稿向電腦端 `/event` 送 `Content-Type: application/json`：

| 事件 | 欄位 | 發送時機 |
| --- | --- | --- |
| `light_update` | `device`, `event`, `lux` | BH1750 可用時約每 10 秒一次；lux 取一位小數 |
| `motion_detected`、`motion_cleared` | `device`, `event` | PIR 暖機 60 秒後，僅在狀態變化時 |
| `button_pressed` | `device`, `event` | 按鈕去彈跳後按下時 |

草稿中的 HTTP timeout 為 800 ms，Serial 輸出事件名及 HTTP 狀態碼。使用者回報已實際遮光及在 PIR 前走動，測試「沒問題」。本次沒有取得序列埠輸出、lux 數值、事件接收紀錄或 HTTP 回覆碼；此回報列為**使用者人工硬體測試**，不是代理可獨立量測的通過證據。草稿中的 Wi-Fi 設定不複製到此報告。

## 本機唯讀觀測

- `Get-NetTCPConnection -LocalPort 8765 -State Listen`：`0.0.0.0:8765` 由 `python.exe` 監聽，PID 46860（當次快照，程序識別碼可能改變）。
- `Test-NetConnection -ComputerName <configured-LAN-IP> -Port 8765 -InformationLevel Quiet`：`True`。
- 以 `Get-NetTCPConnection -LocalPort 8765 -RemoteAddress <sensor-peer>` 比較 30 秒前後的 TCP 連線記錄：開始 16 筆、結束 20 筆，期間發現 7 筆此前未見的連線。這只證明該區網對端有新的 TCP 連線，不等於 7 個 HTTP 200 或 7 筆有效 JSON；TIME_WAIT 快照也不能當作完整流量計數。
- GET 根路徑回 `501 Unsupported method ('GET')`，沒有可讀狀態頁。未發送合成 POST，避免污染實際設備資料。
- 搜尋目前正式 source：沒有 SIRO `/event` HTTP ingress；既有 [MQTT 單次閉環驗收](../../ESP32_MQTT_VERIFICATION.md) 是獨立路徑。電腦端接收器來源與持久紀錄尚未定位。

## 未通過／未驗證

尚無可核對的 light_update lux 前後變化、motion_detected/motion_cleared payload、HTTP 2xx 狀態、接收時間與有效期，也無 World State 來源觀測。因而只能說電腦可接受該埠的連線且使用者回報感測器動作正常。沒有驗 MQTT 驗證／離線／去重、HA、LED 命令及 readback；[A18](../../ACCEPTANCE.md) L3 仍待真閉環證據。沒有修改執行程式、安裝依賴、控制設備或執行自動測試。

下一步需取得電腦端接收程式或其事件日誌的路徑，唯讀核對事件類型、lux 變化、時間與回應碼；若要接進 SIRO，先確認 HTTP 與既有 MQTT 設備契約的關係，再寫相應契約測試及實作。
