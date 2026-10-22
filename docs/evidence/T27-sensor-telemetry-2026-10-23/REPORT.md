# T27 ESP32 MQTT 動作與光度遙測

日期：2026-10-23 Asia/Taipei。結果：**BUILD_VERIFIED + SYNTHETIC_INTEGRATION_VERIFIED / HARDWARE_PENDING / BLOCKED_SYNC**。

## 範圍

以 `origin/main` `89b80fbf17dee5e311c5f1c3123cb92833b6cc68` 為基線，在獨立 worktree 更新原有 ESP32 MQTT firmware：PIR 經 60 秒暖機、500 ms 穩定後作 `motion` boolean，BH1750 經 `Wire` 作 `illuminance` lux。兩者跟 `power` 共用帶 `observed_at_epoch` 的 retained `state`，每 10 秒刷新，PIR 邊緣即時發送。I²C 失敗時省略光度；Broker 重連時先撤銷舊感測快照，避免重貼時間戳。原 LED `light.set`／ACK／readback、已認證 MQTT topic 與依賴 pin 保留。

PIR 低電平只表示目前沒有動作，不是無人，故屬性名為 `motion`，不把它直接當 `presence` 觸發房間場景。板型、GPIO 與 I²C 腳位須按實板設定；新功能**沒有**刷入使用者設備，也沒有修改其獨立 HTTP receiver。未新增第三方 firmware 函式庫：`Wire` 已在 Arduino framework，BH1750 連續高解析命令 `0x10` 與 raw/1.2 參考 [ROHM 技術資料](https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf)。

## 已執行驗證

| 層級 | 命令／結果 |
| --- | --- |
| 主機端時序與換算 | `PYTHONPATH=src .../venv/bin/pytest -q tests/integration/test_esp32_sensor_telemetry.py`：PIR 暖機、去彈跳、`millis()` 回捲、重連失效／重採與 BH1750 換算；含真 broker synthetic state → `MqttStateProjector` → SQLite World 來源及 20 秒失效。 |
| 相鄰回歸 | 使用專案 `.python-version` 3.14.4 的現有 venv，`pytest -q tests/integration/test_esp32_sensor_telemetry.py tests/integration/test_mqtt_gateway.py tests/integration/test_mqtt_time_formats.py tests/integration/test_esp32_mqtt_probe.py tests/integration/test_device_registry.py tests/integration/test_room_automation.py`：**68 passed／33.13s／exit 0**。新測試 2，真 Broker／World 使用合成裝置與資料，非實板。 |
| 靜態檢查 | `ruff check`、`ruff format --check` 新測試 PASS；`mypy tests/integration/test_esp32_sensor_telemetry.py` PASS；`git diff --check` PASS。 |
| firmware 交叉編譯 | 自有 WSL 目錄，以 `include/secrets.example.h` 作 compile-only `secrets.h`，`PLATFORMIO_CORE_DIR` 隔離，`platformio==6.1.19`、既有 `espressif32@6.12.0`／`esp32dev`／ArduinoMqttClient 0.1.8／ArduinoJson 7.4.2：最終 source 與編譯副本相同，`pio run --project-dir /home/pepepig/.local/share/siro/t27-build-20261023/project --environment esp32dev --jobs 2` **SUCCESS／3.38s 最終增量編譯**（首輪完整編譯 38.02s）。RAM 45,652／327,680，Flash 797,265／1,310,720；`firmware.bin` 803,840 bytes，SHA256 `2a626a3e563f8ac8ff90739b7d0e023d51b0b6c8c6ad16f2b2a452f2df8326c7`。僅供驗證，未燒錄。 |

失敗亦保留：第一次以 `uvx` 的隔離 PlatformIO 執行，內部 esptool 安裝需要 `pip` 而該環境未提供，於 compiler 前因不完整 package manifest 失敗。只清理本次隔離目錄中的 `tool-esptoolpy` partial package，改用含 `pip` 的隔離 venv，原 source、平台及依賴 pin 不變。3.12 venv 跑原 `test_mqtt_gateway.py` 的 broker/LWT 案例逾時；同案在專案要求的 Python 3.14.4 獨立重跑 **2 passed／2.43s**，再與 68 項合跑通過。沒有把初次失敗寫成通過。

編譯副本、example-only `secrets.h`、工具鏈與 binary 都曾位於明確自有的 WSL 目錄 `/home/pepepig/.local/share/siro/t27-build-20261023`；核對最終大小及 SHA 後已回收整個 1.6 GiB 目錄與兩個空暫存目錄。Git 只保存 source／測試／文字證據，不保存可誤刷的 binary。

## 交付限制與下一步

正式 SIRO 啟動流程尚未連接 MQTT projector，這輪 World State 成功只在真 Broker＋合成 state 的整合測試中成立。真板型號、GPIO、BH1750 I²C、PIR 暖機／動作、NTP、MQTT pairing、LED 視覺 readback、斷線回復與 HA/A18 L3 均待實體驗收；不能把交叉編譯或舊 HTTP receiver 的 200 當成這些項目通過。沒有讀取／提交真 Wi-Fi、MQTT 密碼或私人 sensor log。

GitHub 未結 Issue／PR 在開始時查得為空；GitHub 寫入 API 回 401，故尚未完成線上認領／推送／Draft PR。保留獨立本地分支及 [協作交接](../../collaboration/T27-ESP32-SENSOR-TELEMETRY.md)，不得宣稱其他電腦已能讀取。恢復寫入後先重查競爭認領，再推分支開 Draft PR；由整合者更新共享 `docs/STATUS.md`。產品下一張切片是設備配對與正式 MQTT projector 啟動接線，另需實板 flash／人工驗收。
