# T27 驗收證據

日期：2026-09-25｜結果：PASS（authenticated TCP broker + simulator）；ESP32 HARDWARE NOT TESTED

- 鎖定 aMQTT 0.12.1 與 aiomqtt 2.5.1，以 loopback 真 TCP broker 測試。FileAuthPlugin 使用
  Argon2 password file且不載入 anonymous plugin；錯誤密碼連線被拒。
- crash client 設定 retained LWT `offline`，程序被終止後 observer 真實收到 availability。
  state/availability 可 retained；`command_message()` 固定 command retain=false。
- 測試刻意植入 retained command，重連 simulator 收到 retain flag 後拒絕，不執行舊動作；
  live command 接受，重複 command ID 不重做，過期 command 拒絕。
- `CommandTracker` 將 pending、acknowledged、confirmed 分開；ack 後仍非成功，只有 matching state
  readback 才 confirmed。
- `firmware/esp32` 提供 ESP32 DevKit＋板載 LED PlatformIO source、Wi-Fi/MQTT auth、retained
  LWT/state、非 retained ack、command expiry/dedup/retain rejection與接線指南。此主機沒有
  PlatformIO/Arduino CLI 或實體板，因此未編譯、燒錄或宣稱硬體通過。

官方依據：[aMQTT packaged auth plugins](https://amqtt.readthedocs.io/en/latest/plugins/packaged_plugins/)、
[aiomqtt retained messages](https://aiomqtt.bo3hm.com/publishing-a-message)、
[ArduinoMqttClient retained flag API](https://github.com/arduino-libraries/ArduinoMqttClient/blob/master/src/MqttClient.h)。

證據：`tests/integration/test_mqtt_gateway.py`、`tests/helpers/mqtt_crash_client.py`、
`src/siro/services/devices/mqtt.py`、`firmware/esp32/`。
