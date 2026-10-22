# SIRO ESP32 MQTT 範例

狀態：2026-10-23 感測版已以 PlatformIO Core 6.1.19／既有 pinned `esp32dev` 設定完成真實交叉編譯；實體板燒錄／NTP／目視 LED 與感測器仍待驗。

本版使用隔離編譯環境與 example 帳密，RAM 45,652／327,680 bytes，Flash
797,265／1,310,720 bytes；沒有燒錄或把 binary 納入 Git。新版本命令與限制見
[感測版證據](../../docs/evidence/T27-sensor-telemetry-2026-10-23/REPORT.md)；
[前版編譯證據](../../docs/evidence/T27-firmware-build-2026-10-16/REPORT.md)保留作歷史。

此範例使用 ESP32 DevKit 內建 LED（預設 GPIO 2）作低風險 actuator，另支援 PIR 動作與
BH1750 光度感測器。複製
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

## 感測資料與接線

在被忽略的 `include/secrets.h` 依**實際板型**設定 `SIRO_PIR_PIN`、
`SIRO_I2C_SDA_PIN`、`SIRO_I2C_SCL_PIN`、`SIRO_BH1750_ADDRESS`。範例值是
ESP32 DevKit 的 PIR GPIO 27、I²C SDA 21／SCL 22、BH1750 位址 `0x23`；其他
ESP32 變體可能使用不同腳位，先核對板型與接線再燒錄。PIR VCC/GND/OUT 接板子
允許的電壓與輸入腳位；BH1750 接 3.3V/GND/SDA/SCL，注意模組規格與 I²C 拉高電壓。
原使用者草稿的 PIR GPIO 5 不直接作此 `esp32dev` 範例預設：Espressif 將 GPIO 5
列為 ESP32 啟動 strapping pin；[官方接線指南](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/schematic-checklist.html)
要求注意開機時的腳位電位。實際板型不同時仍須重新核對。

firmware 維持原有 `state` topic 與 `power` readback，並在同一份有
`observed_at_epoch` 的狀態中選擇性加入：

| 屬性 | 何時提供 | 意義 |
| --- | --- | --- |
| `motion`（boolean） | PIR 啟動 60 秒暖機後，首筆與穩定 500 ms 的變化 | 當前 PIR 輸出；`false` 只代表目前沒有動作，**不能**推斷房間無人 |
| `illuminance`（number，lx） | BH1750 I²C 成功讀到兩個位元組後 | 16 位原始值除以 1.2；讀取失敗不重用舊值 |

每 10 秒發布最新狀態，PIR 穩定邊緣另即時發布。PIR 暖機前不宣稱 `motion=false`；
BH1750 缺席／讀取失敗時省略 `illuminance`，而非填入零。sensor 值只經既有已認證
MQTT 設備路徑上報，不額外開 HTTP 入口，也不影響 `light.set` ACK 後的 LED readback。
MQTT 重新連線時先撤銷舊感測快照；PIR 需重新穩定 500 ms，BH1750 需下一次成功
讀取，才會跟新的時間戳一起發出。
若為 World State 建立 descriptor，`motion` 設 boolean、`illuminance` 設 number／`lx`，
`availability_ttl_ms` 可用 20,000 配合 10 秒刷新；位置與 privacy 依部署實際設定。
目前正式 SIRO 啟動程序尚未接入此 MQTT projector，不能只因 firmware 上報就宣稱
產品已感知動作或光度。

BH1750 命令 `0x10`（連續高解析模式）、首次量測等待及 lux 換算依
[ROHM BH1750FVI 技術資料](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf)。
使用 Arduino 平台既有 `Wire`，未新增第三方函式庫或變更 `platformio.ini`。
先前使用者的獨立 HTTP 草稿仍可單獨運作；這份 MQTT firmware 不是自動更新，
**尚未燒錄使用者實板**。

真 Broker 的單次 Python 閉環驗收與操作限制見
[ESP32 MQTT 驗收指南](../../docs/ESP32_MQTT_VERIFICATION.md)。本機 client 使用
`127.0.0.1:1883`（Broker 可監聽 `0.0.0.0:1883`），只發布一次 `light.set {"power": true}`，
必須收到同 ID 的 `applied` ACK 與新的 `power: true` state 才確認。驗收會點亮 LED，
不自動重送或另送關燈；Broker／合成設備通過不能取代真板編譯、燒錄與 LED 驗證。

接線：使用板載 LED 時不需外接。改用外接 LED 時，GPIO → 220–330 Ω 電阻 → LED 陽極，LED
陰極 → GND；依板型修改 `SIRO_LED_PIN`。不可直接驅動市電、馬達或大電流負載。

正式 LAN 部署需 TLS 或隔離可信網段、每設備 ACL 與可撤銷憑證。此 simulator broker 僅綁
127.0.0.1，不代表明文帳密適合 LAN。
