# SIRO ESP32-S3 感測節點範例

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
| `motion` | PIR 暖機 60 秒後上報；變化需穩定 500 ms。`false` 僅表示目前未偵測動作，不表示無人。 |
| `illuminance` | BH1750 每 10 秒讀取，原始值除以 1.2 得 lx；讀取失敗就省略。 |
| `button_down` | `INPUT_PULLUP`，按下為 true；穩定 50 ms 的變化即時上報。 |
| `button_press_count` | 每次穩定按下加一；開機歸零，不能用它跨重啟計數，也不觸發動作或授權。 |

每 10 秒重發狀態。MQTT 重連時先撤銷 PIR 與光度的舊觀測；按鈕狀態仍來自本機採樣。連線阻塞期間的短按可能漏記，故它不是可靠的緊急控制通道。所有值帶 `observed_at_epoch`，World State descriptor 應設定 20 秒有效期與 `LOCAL_ONLY` privacy。此 firmware 使用已認證 MQTT；使用者目前燒在實板的獨立 HTTP 草稿不會自動換成此版本，正式 SIRO 啟動程序也尚未接入 MQTT projector。

原有 `esp32dev`／LED 範例仍可作可選編譯；只有確認 LED 實際存在與腳位後，才把 `SIRO_HAS_LED` 設為 `1`。此時恢復 `light.set` 的 command／ack／`power` readback。**此路徑不適用使用者目前的無 LED 實板，也不算 T27 LED 硬體驗收。**

BH1750 命令與 lux 換算參考 [ROHM 技術資料](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf)。沒有新增 firmware 依賴；正式 LAN MQTT 仍需隔離網段或 TLS、每設備 ACL 與可撤銷憑證。編譯與整合測試證據見[本輪報告](../../docs/evidence/T27-sensor-telemetry-2026-10-23/REPORT.md)。

## MQTT 優先、HTTP 備援與 SIRO 端啟用

韌體每 5 秒嘗試一次 MQTT；連續 `SIRO_MQTT_FALLBACK_AFTER_MS`（預設 30 秒）連不上就改以舊接收器格式 POST 到 `SIRO_HTTP_FALLBACK_URL`（`light_update`／`motion_*`／`button_pressed`），MQTT 恢復後自動切回。MQTT 與 HTTP 使用**不同 device ID**（建議 MQTT `siro-node-mqtt-01`、HTTP `siro-node-01`），避免 registry 的 adapter 衝突。**此備援與 MQTT 路徑尚未編譯或上板驗證**（本機無 PlatformIO／arduino-cli 與 ArduinoMqttClient、ArduinoJson）。

SIRO gateway 預設不訂閱 MQTT。啟用：`SIRO_ESP32_MQTT_ENABLED=1`、`SIRO_ESP32_MQTT_HOST`，可選 `SIRO_ESP32_MQTT_PORT`（1883）、`SIRO_ESP32_MQTT_USERNAME`／`PASSWORD`、`SIRO_ESP32_MQTT_DEVICE_ID`（預設 `siro-node-mqtt-01`，不可與 HTTP ID 相同）、`SIRO_ESP32_MQTT_LOCATION`。只訂閱該設備的 `state`／`availability`，忽略 retained state；broker 不通時背景重連，不影響 gateway。
