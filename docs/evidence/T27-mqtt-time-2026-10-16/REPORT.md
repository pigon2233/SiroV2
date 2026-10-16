# T27-FIX-01 — MQTT／ESP32 時間相容修復

日期：2026-10-15 開始，2026-10-16 完成局部驗收。狀態：**LOCAL_VERIFIED / HARDWARE PENDING**。
來源為使用者指定的三項 MQTT 修復；不是新 runtime 架構或完整 T27 真硬體完成。

## 問題與最小修復

| 已確認根因 | 實作 |
|---|---|
| Python 命令只輸出 ISO，但 firmware 讀 `expires_at_epoch`，缺欄位會視為到期 | `command_message` 保留 ISO 並加整數 epoch；non-retained 不變 |
| 原 strict simulator 會拒絕新增 mirror | 僅解包這個已知欄位，核對非 bool 整數及與 ISO 一致；其他 unknown fields 繼續拒絕，舊命令仍可用 |
| ESP32 發數值 `observed_at_epoch`，projector 只認 ISO | ISO 欄位存在時仍優先且必須有效；缺省才接受 int／float epoch，以 UTC 解析；bool、非有限值、越界、naive ISO 在 registry mutation 前拒絕 |
| `configTime` 只啟動 SNTP，原 setup 立即連 MQTT | 等待有效時鐘，30 秒超時 restart＋return；loop 另有 clock guard，避免 setup 失敗後繞過 |
| 需要可執行的真 Broker 閉環驗收 | 新增 `scripts/verify_esp32_mqtt.py`，使用既有 aiomqtt／CommandTracker／MqttStateProjector／Registry／臨時 SQLite WorldModel |

原 repository 的實際名稱是 `CommandTracker`，不存在 `MqttCommandTracker`；直接重用，沒有為命名要求再加一層類別。

對時行為已核對鎖定 Arduino ESP32 2.0.17 的
[官方 configTime／getLocalTime 實作](https://raw.githubusercontent.com/espressif/arduino-esp32/2.0.17/cores/esp32/esp32-hal-time.c)；
aiomqtt 的官方 API 核實列在操作指南。

單次 probe 先完成 ack/state 訂閱，才發布唯一一筆非 retained `light.set {"power": true}`。
只有同 command ID 的 `applied` ACK，以及本次新鮮、型別正確、無矛盾的 `power:true` readback
俱足，且真正 WorldModel 投影相符，才進 `DeliveryState.CONFIRMED`。ACK-only 為 ACKNOWLEDGED，
state-only 為 PENDING；逾時與連線問題均 unknown／非零退出，不自動重送。

## 實際驗證

環境：現有 `.venv` Python 3.14.4、既有 aiomqtt／amqtt；沒有安裝或更動依賴。

1. 原始 `HEAD:src/siro/services/devices/mqtt.py` 載入獨立 Python process，沒有改工作區檔案，
   跑新時間格式測試為 **5 failed / 28 passed / 0.19s**。失敗為兩個 command epoch 缺欄位、
   兩個 epoch state 無法投影、naive ISO 在寫入前未拒絕；見 [原始 RED](BASELINE_RED.txt)。
   基準 HEAD 為 `215aaa9d305073b41a44f242387051ea836dc035`。
2. 新時間格式 **33 passed**，驗證 ISO／offset／fractional epoch、真正 Registry／SQLite
   投影、mirror 型別及一致性、未知欄位、無效時間在寫入前拒絕。最後收緊「數值相等但為 float
   的命令 mirror」後亦 **33 passed / 0.29s**。
3. probe **22 cases** 使用自有隨機 loopback port 的真 amqtt Broker、真 aiomqtt CLI 子程序、
   合成 ESP32 peer。涵蓋 ACK/state 反序、ACK-only／state-only、錯 ID/topic/status、retained、
   過舊／未來／壞時間、額外 property、同秒矛盾、較新觀測解除矛盾及單次發布。
   每個 CLI 正常／失敗結束都驗證臨時 SQLite 清除；Broker、peer、子程序均由 fixture 收尾。
4. 最後相關回歸命令涵蓋以下七檔，**71 passed / 18.38s**，無 failed／skipped：

   ```bash
   .venv/bin/pytest -q \
     tests/integration/test_mqtt_time_formats.py \
     tests/integration/test_mqtt_gateway.py \
     tests/integration/test_device_registry.py \
     tests/integration/test_esp32_mqtt_probe.py \
     tests/integration/test_identity_world.py \
     tests/integration/test_home_assistant.py \
     tests/contract/test_boundaries.py
   ```

5. [Host clock harness](verify_clock_gate.py) 抽取實際 firmware 的 wait/setup/loop 函式，
   以 Arduino stubs 及 `g++ -std=c++17 -Wall -Wextra -Werror` 執行：**9 情境 PASS**。
   包含已同步、延後同步、臨界值未就緒、millis 溢位、setup 成功／逾時重啟、loop 阻擋／恢復／
   時鐘失效。臨時編譯輸出自動清除。這不是完整 firmware build。
6. 本卡五個 Python 檔（MQTT service、probe、兩個新 test、host evidence harness）的 Ruff
   format／check 與 mypy 全 PASS；`git diff --check` PASS；四個本卡程式／測試檔的 detect-secrets 掃描0 findings。未宣稱整個 `scripts/check`、遠端 CI 或發布已通過。

## Review 發現與修正

獨立唯讀 review 找出 probe 首稿兩個問題，均在新增腳本內修復：

- ACK 原本只更新旗標，timeout 仍報 PENDING；改為有效 ACK 到達即 acknowledge，確認時只 observe_state。
- 同秒 true／false 會受既有 World observation UUID 排序影響，可能誤確認。probe 保留本次最新
  wire 候選；同 timestamp 矛盾時保持 ambiguous，直到較新觀測解除。確認時核對候選與 World
  time/value 一致。兩種同秒順序均有真 Broker 回歸，未修改 Core 排序或加入永久狀態。

最終獨立唯讀 review 另以真 SQLite／Registry／Projector、記憶體 MQTT stub、固定 UUID
`2→1` 重跑原反例：同秒 true→false→ACK 現為 unknown／acknowledged／ambiguous，
ACK-only 現為 unknown／acknowledged；原兩 finding 已解，沒有剩餘 scoped blocker。
這項獨立反例測試沒有連 Broker 或真設備，與上述真 Broker 測試分開取證。

## 本機 1883 與真硬體限制

實際嘗試 `127.0.0.1:1883 --timeout 1`：**exit 1 / result unknown / publish_attempts 0**，
原因 `mqtt_error_unknown_do_not_retry_automatically`。未啟動替代 Broker、未發硬體指令；
結束時只讀核對仍無 listener，見 [環境與保留檢查](ENVIRONMENT.json)。
`0.0.0.0` 是 Broker listen address；本機 client 用 `127.0.0.1`，腳本也接受前者並轉為 loopback。

沒有 PlatformIO toolchain，**完整 ESP32 編譯／燒錄／真 NTP／GPIO／目視 LED 均未驗證**。
真 Broker＋合成 peer 成功只證明軟體協定閉環；A18 和 T27 的 HARDWARE PENDING 保留。
epoch 只有秒精度，不能完全區分同秒其他 writer 的效果；此工具用於單一受控驗收，
不冒稱多 writer 仲裁。`hardware_verified:false` 亦明示 MQTT/GPIO payload 不等於人工目視。
timeout 僅涵蓋網路階段，初始化 schema 在其外，不宣稱整 CLI 三秒完成。

## 範圍、使用與回退

操作步驟、帳密環境變數及點亮後不自動關燈的行為見
[ESP32 MQTT 驗收指南](../../ESP32_MQTT_VERIFICATION.md)；韌體步驟見
[firmware README](../../../firmware/esp32/README.md)。

Production 僅改 MQTT service 與 firmware 兩處；沒有 Core／DB schema／授權／provider／UI／
依賴變更，沒有存取 live 8026 或私人資料。既有未提交 UI 以 SHA256 核對完全保持，
其餘預存修改與證據沒有清除或納入本卡聲稱。

回退只反向撤本卡 `mqtt.py` 的時間相關 hunk 與 firmware clock gate，同時移除新增 probe／
兩個新測試並退回對應文件敘述；保留現有 DB／設備／所有其他工作區修改。
已燒錄板需另以原 firmware 重燒；本次沒有燒錄。回退將恢復原本 epoch 不相容缺陷，
應停止這條硬體驗收路徑，不能以還原 DB 補救。沒有更改既有 RT 編號、任務 ranking 或全域 architecture。
