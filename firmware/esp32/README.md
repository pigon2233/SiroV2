# SIRO ESP32 MQTT 範例

狀態：2026-10-16 已以 PlatformIO Core 6.1.19／既有 pinned `esp32dev` 設定完成真實交叉編譯；實體板燒錄／NTP／目視 LED 仍待驗。

編譯使用自建暫存環境與 example 帳密，來源未改，RAM 45,276／327,680 bytes，Flash
777,901／1,310,720 bytes。編譯產物僅供驗證，沒有燒錄或納入 Git；重現、工具版本與清理見
[編譯證據](../../docs/evidence/T27-firmware-build-2026-10-16/REPORT.md)。

此範例使用 ESP32 DevKit 內建 LED（預設 GPIO 2）作低風險 actuator。複製
`include/secrets.example.h` 為被 Git 忽略的 `include/secrets.h`，設定 Wi-Fi、loopback/LAN MQTT
broker、每台裝置獨立帳密與 `SIRO_DEVICE_ID`，再執行：

```bash
pio run
pio run --target upload
pio device monitor
```

topic：`siro/devices/{id}/{state|availability|command|ack}`。availability/state retained；command/
ack 不 retained。LWT 為 retained `offline`。firmware 明確拒絕 retained command、過期 command、
重複 command ID 與非 `light.set` action；ack 後另發 state，gateway 必須以 state readback 判定成功。

命令同時帶 ISO `expires_at` 與整數 `expires_at_epoch`；firmware 以後者檢查到期。
state 使用 UTC 秒數 `observed_at_epoch`，Python gateway 同時支援此格式與原 ISO
`observed_at`。啟動時呼叫 `configTime` 後最多等 30 秒，直到
`time(nullptr) > 1700000000` 才連 MQTT；對時逾時重啟，主迴圈亦禁止時鐘未就緒時連線。

真 Broker 的單次 Python 閉環驗收與操作限制見
[ESP32 MQTT 驗收指南](../../docs/ESP32_MQTT_VERIFICATION.md)。本機 client 使用
`127.0.0.1:1883`（Broker 可監聽 `0.0.0.0:1883`），只發布一次 `light.set {"power": true}`，
必須收到同 ID 的 `applied` ACK 與新的 `power: true` state 才確認。驗收會點亮 LED，
不自動重送或另送關燈；Broker／合成設備通過不能取代真板編譯、燒錄與 LED 驗證。

接線：使用板載 LED 時不需外接。改用外接 LED 時，GPIO → 220–330 Ω 電阻 → LED 陽極，LED
陰極 → GND；依板型修改 `SIRO_LED_PIN`。不可直接驅動市電、馬達或大電流負載。

正式 LAN 部署需 TLS 或隔離可信網段、每設備 ACL 與可撤銷憑證。此 simulator broker 僅綁
127.0.0.1，不代表明文帳密適合 LAN。
