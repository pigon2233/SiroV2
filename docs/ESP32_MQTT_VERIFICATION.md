# ESP32 MQTT 單次閉環驗收

`scripts/verify_esp32_mqtt.py` 使用專案既有的 `aiomqtt`，透過真 MQTT 連線驗收一筆
`light.set`。它不是常駐 gateway，也不會改動 SIRO 正式資料庫或自動重送指令。
執行這個腳本會把指定裝置的 LED 設為開啟；驗收後保留該狀態，不另送關燈指令。

## 前置條件與執行

2026-10-16：既有 `esp32dev` pinned 設定已在自建暫存環境完成真交叉編譯，
[工具版本與結果](evidence/T27-firmware-build-2026-10-16/REPORT.md)可核對；使用 example 設定，
尚未燒錄或操作實板。以下 broker／NTP／LED 前置條件仍需在實際驗收時成立。

- MQTT broker 已啟動，ESP32 已設定相同 broker／帳密／device ID 並完成 NTP 對時。
- 裝置為使用者授權的低風險測試 LED；broker ACL 允許 command 發布及 ack/state 訂閱。
- 使用專案既有虛擬環境，不新增或下載依賴。

broker 可監聽 `0.0.0.0:1883`，本機 client 應連 `127.0.0.1:1883`。
`--host 0.0.0.0` 會明確轉為 `127.0.0.1`；其他 host 則依傳入值連線。
腳本不會自行啟動、重新設定或取代 broker。

```bash
uv run python scripts/verify_esp32_mqtt.py
```

可選參數：

```bash
uv run python scripts/verify_esp32_mqtt.py \
  --host 127.0.0.1 --port 1883 --device-id esp32-lab-01 --timeout 3
```

帳密從 `SIRO_MQTT_USERNAME`／`SIRO_MQTT_PASSWORD` 環境變數讀入；不要把真密碼放入
命令列、版本控制或驗收附件。腳本不輸出帳密，也不輸出 broker 例外原文。
此腳本使用 TCP，跨可信測試網段的正式部署仍需獨立處理 TLS 與 ACL。

## 成功必須同時具備的證據

1. 訂閱精確的 `siro/devices/esp32-lab-01/ack` 與 `.../state` 並取得訂閱回執後，
   向 `.../command` 發布唯一一筆非 retained、QoS 1 的 `light.set`，
   `desired_state` 為 `{"power": true}`，到期時間同時含 ISO 與 epoch。
2. 收到非 retained、相同 `command_id` 且 `status: "applied"` 的 ack，既有 tracker
   立即推進至 `ACKNOWLEDGED`。只有 ack、缺少 state 時仍不得稱為確認成功。
3. 收到非 retained 的新鮮 `properties.power: true` state。支援既有含時區 ISO
   `observed_at` 及 ESP32 的數值 `observed_at_epoch`；禁止 bool 充當 epoch 或 power。
4. 真實 `MqttStateProjector` 將該 payload 經 `DeviceRegistry` 寫入臨時 SQLite
   WorldModel，產生 `device:esp32-lab-01:esp32_mqtt` 來源的有效觀測。
5. 腳本保留本次收到的最新合法 wire state；較舊的觀測不覆蓋候選，同一 timestamp
   出現矛盾 power 時標記 `state_ambiguous: true`，只有更新 timestamp 的觀測才能解除。
   最新候選無矛盾、power 為 true，且真實 WorldModel 的時間／值與候選一致後，才呼叫
   `CommandTracker.observe_state`。狀態到達 `DeliveryState.CONFIRMED`，輸出 JSON 並以 0 結束。

state 先到、ack 後到也可驗收；ack 單獨到達、舊 retained 快照、錯 command ID、錯裝置
topic、未達 desired_state、錯誤型別、過期或明顯未來的觀測均不能確認成功。
拒絕的 ACK 會回報 `delivery_state: "failed"`、`result: "unknown"`，仍以非零退出；
未知 ID 不改本次追蹤。已收 `applied` 後晚到的 `duplicate` 不降級，可繼續等 state；
沒有先收 `applied` 的 duplicate 不算受理。晚到 unsupported／expired 等矛盾回覆仍保守退出。
這裡的 wire 成功字串是 `applied`；simulator 的 `CommandResult.ACCEPTED` 值 `accepted`
不能代替裝置 ACK。tracker RAM 預設最多1024筆，issue清理terminal／expired，滿active拒新；
它不提供持久歷史，腳本亦不新增背景清理服務。
若 payload 帶有 `observed_at`，必須是有效含時區 ISO 字串；無此欄位才可使用 epoch，
不得以有效 epoch 繞過損壞的 ISO 欄位。
ESP32 epoch 僅有一秒精度，因此可接受指令送出所在秒的觀測；未來偏移上限一秒，且不超過
本次指令到期時間。這是此 firmware wire format 的解析界限，不能證明同一秒其他 writer
產生的相同狀態屬於本指令；因此只適用於單一受控驗收，不等同一般多 writer 仲裁協定。

預設整段 MQTT 連線／訂閱／發布／收取限 3 秒，`--timeout` 範圍為 0.1–60 秒。
沒有 broker、拒絕執行、斷線或逾時時輸出 `result: "unknown"`，以非零結束；
**不能把 unknown 當作燈沒開，也不能自動重跑**。先人工確認裝置狀態及連線，再決定下一步。
QoS 1 可能有協定重傳，命令的唯一 ID 與 firmware 去重仍然必要。

輸出的 `hardware_verified: false` 表示 MQTT/GPIO 回讀不等於人工確認實際 LED、接線或
負載安全。真板 NTP／編譯／燒錄／目視 LED 結果需另記；合成設備成功只能稱整合測試成功。

## 自動測試

```bash
uv run pytest -q tests/integration/test_esp32_mqtt_probe.py
```

測試使用自有隨機 loopback port 的真 `amqtt` broker、真 `aiomqtt` client 和 CLI 子程序，
僅用合成 ESP32 對等端回覆 firmware 格式；不連本機 1883，也不接觸真硬體。
涵蓋 ISO／epoch、ack/state 順序顛倒、初始 retained 狀態、缺少一半回覆、錯誤 ack、late duplicate、
拒絕執行、舊／未來／無效 state、錯 topic、缺少 broker及單次發布；另驗同一 epoch 秒內
true→false／false→true 矛盾不能確認，較新觀測可解除矛盾並與投影一致後確認。

## 官方 API 核實

- [aiomqtt Developer interface](https://aiomqtt.bo3hm.com/developer-interface)：
  `Client` 非同步 context manager、bounded incoming queue、`subscribe`、
  `publish(..., qos=1, retain=False)` 與 `messages`。
- [aiomqtt Subscribing to a topic](https://aiomqtt.bo3hm.com/subscribing-to-a-topic)：
  訂閱與迭代接收訊息的官方使用方式。

這些介面使用專案既有 `aiomqtt>=2.5,<3`，沒有新增 SDK 或平行設備抽象。
