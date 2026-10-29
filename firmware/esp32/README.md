# SIRO ESP32-S3 感測節點範例

## 目前狀態（韌體 1.0.3，2026-10-29）

- **版本／發佈：** `include/ota.h` 預設 `SIRO_FW_VERSION 1.0.3`；USB 已燒入 COM3 並在實板觀察（uptime 連續、free_heap 約 257–270 KB 穩定、主迴圈最大間隔約 36 ms）。OTA 映像暫存於 `siro-ota-staging/1.0.2`，**未發佈 manifest**；`pir_rawtest` 標 1.0.9，僅供 PIR 原始訊號台測。
- **架構：** `loop()` 只做 PIR／按鈕／BH1750／OLED，不等網路；Wi-Fi、NTP、MQTT、HTTP 備援、OTA 在另一核心的 `netTask`，以快照交換。沒有任何自動 `ESP.restart()`；Wi-Fi 以指數退避（5→60 s）、MQTT 以 5→30 s 退避重連，MQTT 連上即發完整 state 快照。
- **MQTT／HTTP 備援：** MQTT（設備 ID `siro-node-mqtt-01`）失聯 30 秒後改 POST 舊接收器（`siro-node-01`），先補送目前 motion 快照，之後狀態變更或失敗時每 ≥2 s 重試，MQTT 恢復自動切回。實測關 broker 約 35 s 切 HTTP，開回後 ≤30 s 切回。
- **PIR 判定：** 這顆 PIR 有人活動時輸出約 1 s HIGH／2–3 s LOW 的週期脈衝，故不看單一脈衝長度：raw 去抖 150 ms 記一個脈衝；10 s 窗口內 ≥2 個脈衝、或 HIGH 占空 ≥15%、或單次 HIGH ≥1.5 s 即判有人；之後保持 25 s，期間有新證據續期。常數集中在 `sensor_telemetry.h` 的 `kPir*`。診斷 topic `siro/devices/<id>/diag`（每 10 s，QoS0）含 `pir_*`、`rssi`、`wifi`、`mqtt`、`uptime_s`、`free_heap`、`fw`。
- **顯示：** SSD1306 128×64（I²C 0x3C）小臉：待機眨眼／看／哈欠／打瞌睡，偵測到動作→驚訝，按鈕→愛心，光線突變→瞇眼，斷線→睡覺／困惑；角落有 Wi-Fi 格數、M／H／- 連線狀態與 lux。`SIRO_HAS_OLED=0` 可停用；螢幕缺席不影響感測。
- **SIRO 端：** gateway 的 MQTT 訂閱端預設關閉（`SIRO_ESP32_MQTT_ENABLED=1`）；`SIRO_ESP32_MQTT_DIAG_LOG=1` 另把 diag 寫入資料目錄 `esp32-diag.jsonl`（上限約 4 MB，保留一份 `.1`）。`GET /v1/devices/esp32/state` 多一個 `mqtt` 區塊。`NodeHealthWatcher` 把 MQTT 與 HTTP 設備視為同一顆節點。這些都需重啟 gateway 才生效。
- **已知限制：** 目前 Wi-Fi 鏈路品質差（RSSI 約 -63～-77 dBm，從 PC ping 曾量到 30% 封包遺失，之後一次 8%），MQTT 訊息會成批延遲數秒到約 30 秒，動作通知可能晚到；本機偵測與判斷不受影響。改善方式是調整位置／AP／頻道（owner 決定暫不調整）。沒有「Wi-Fi 長時間斷線才重啟」的保險；Wi-Fi 斷線整體測試尚未實機做過。

（以下為較早版本的說明，與本節衝突之處以本節為準。）

使用者現有設備是 ESP32-S3 N16R8，接有 BH1750 光度感測器、PIR 人體動作感測器與一顆按鈕；**沒有 LED**。此版預設 `SIRO_HAS_LED 0`，因此不初始化 LED GPIO、不訂閱 `command`、不發布 `power`／`ack`。超音波感測器尚未安裝，不在本版讀取或宣稱驗收。

複製 `include/secrets.example.h` 為被 Git 忽略的 `include/secrets.h`，填入每台裝置專用 Wi-Fi／MQTT 設定。範例依使用者先前 HTTP 草稿列出 PIR GPIO 5、按鈕 GPIO 4、BH1750 SDA GPIO 8／SCL GPIO 9、I²C 位址 `0x23`；刷機前核對實際板上標示與接線。這些 GPIO 在 [Espressif ESP32-S3 GPIO 文件](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32s3/api-reference/peripherals/gpio.html)中不是 S3 strapping pins。N16R8 為 16 MB QSPI flash／8 MB OPI PSRAM，依 [Espressif Arduino 模組表](https://docs.espressif.com/projects/arduino-esp32/en/latest/troubleshooting.html)設定專用編譯環境；仍須核實模組是 WROOM-1 N16R8 而非其他變體。

```bash
pio run --environment esp32s3_n16r8
# 核對板型、腳位與序列埠後，才可人工刷機：
pio run --environment esp32s3_n16r8 --target upload
pio device monitor
```

`state` topic 為 `siro/devices/{id}/state`，另有 retained `availability`／LWT。感測屬性：

| 屬性 | 行為 |
| --- | --- |
| `motion` | PIR 暖機 60 秒後上報；以窗口內脈衝數／占空比判定並保持（見「目前狀態」）。`false` 僅表示目前未偵測動作，不表示無人。 |
| `illuminance` | BH1750 每 10 秒讀取，原始值除以 1.2 得 lx；讀取失敗就省略。 |
| `button_down` | `INPUT_PULLUP`，按下為 true；穩定 50 ms 的變化即時上報。 |
| `button_press_count` | 每次穩定按下加一；開機歸零，不能用它跨重啟計數，也不觸發動作或授權。 |

每 10 秒重發狀態。MQTT 重連時先撤銷 PIR 與光度的舊觀測；按鈕狀態仍來自本機採樣。連線阻塞期間的短按可能漏記，故它不是可靠的緊急控制通道。所有值帶 `observed_at_epoch`，World State descriptor 應設定 20 秒有效期與 `LOCAL_ONLY` privacy。此 firmware 使用已認證 MQTT；使用者目前燒在實板的獨立 HTTP 草稿不會自動換成此版本，正式 SIRO 啟動程序也尚未接入 MQTT projector。

原有 `esp32dev`／LED 範例仍可作可選編譯；只有確認 LED 實際存在與腳位後，才把 `SIRO_HAS_LED` 設為 `1`。此時恢復 `light.set` 的 command／ack／`power` readback。**此路徑不適用使用者目前的無 LED 實板，也不算 T27 LED 硬體驗收。**

BH1750 命令與 lux 換算參考 [ROHM 技術資料](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf)。沒有新增 firmware 依賴；正式 LAN MQTT 仍需隔離網段或 TLS、每設備 ACL 與可撤銷憑證。編譯與整合測試證據見[本輪報告](../../docs/evidence/T27-sensor-telemetry-2026-10-23/REPORT.md)。

## MQTT 優先、HTTP 備援與 SIRO 端啟用

韌體每 5 秒嘗試一次 MQTT；連續 `SIRO_MQTT_FALLBACK_AFTER_MS`（預設 30 秒）連不上就改以舊接收器格式 POST 到 `SIRO_HTTP_FALLBACK_URL`（`light_update`／`motion_*`／`button_pressed`），MQTT 恢復後自動切回。MQTT 與 HTTP 使用**不同 device ID**（建議 MQTT `siro-node-mqtt-01`、HTTP `siro-node-01`），避免 registry 的 adapter 衝突。2026-10-28 以假 secrets 完成 `esp32s3_n16r8` 編譯（RAM 14.1%／Flash 13.7%）；**尚未上板驗證**。Windows 路徑過長會使編譯器無法啟動，請在短路徑（如 `C:\piow`）建置。

SIRO gateway 預設不訂閱 MQTT。啟用：`SIRO_ESP32_MQTT_ENABLED=1`、`SIRO_ESP32_MQTT_HOST`，可選 `SIRO_ESP32_MQTT_PORT`（1883）、`SIRO_ESP32_MQTT_USERNAME`／`PASSWORD`、`SIRO_ESP32_MQTT_DEVICE_ID`（預設 `siro-node-mqtt-01`，不可與 HTTP ID 相同）、`SIRO_ESP32_MQTT_LOCATION`。只訂閱該設備的 `state`／`availability`，忽略 retained state；broker 不通時背景重連，不影響 gateway。

## OTA 更新（節點端）

`include/ota.h`：secrets.h 定義 `SIRO_OTA_BASE_URL`（如 `http://<PC>:8765/ota`）才啟用。MQTT 連上後與每 6 小時向 PC 中繼（`scripts/esp32_http_receiver.py` 的 `/ota/manifest`、`/ota/firmware`，轉發到 gateway，需 `SIRO_ESP32_OTA_IMAGE`／`SIRO_ESP32_OTA_VERSION`）取 manifest，只接受**嚴格較新**版本；串流寫入另一個 OTA 分區並累計 sha256，**驗證通過才** `Update.end()` 切換分區。新映像在 MQTT 連上前視為「待確認」：開機超過 3 次或 120 秒內未連上 MQTT，就切回舊分區。韌體版本以 `PLATFORMIO_BUILD_FLAGS='-DSIRO_FW_VERSION=\"1.0.1\"'` 指定（預設 1.0.0，並於 `diag.fw` 回報）。第一次必須 USB 燒入含 OTA 的版本。無簽章，只靠 LAN 中繼 IP 白名單＋sha256 防損壞；**尚未上板驗證**。
