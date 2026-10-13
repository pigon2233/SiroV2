# T29 驗收證據

日期：2026-09-26｜結果：PASS（L1 closed-loop simulator）；L3 ESP32 + Home Assistant PENDING

`RoomAutomation` 將已註冊且 online 的 presence 依序投影到 world、建立 home-arrival
salience/candidate、套用 T20 proactivity gates 和 T21 `device.light.set` permission，最後透過
actuator 執行並只在 matching readback 時更新 light state。完整可重現兩個場景與時序輸出：

```bash
uv run python scripts/t29_room_demo.py
```

第一個場景的首次進房會產生 `greet_home` 和 confirmed light；false/true 兩秒 bounce 則產生
`presence_bounce_suppressed`，不會再次問候或切換燈。第二個場景是 manual light readback：
它只更新 world 的 `power=false`，trace 是 `readback_only:manual`，不能反向生成新的 automation
candidate 或 command。

整合測試另覆蓋：room automation 預設停用、T21 policy deny、sensor offline、裝置回讀不相符。
這些情況都不會切換燈或把 command/ack 宣告為成功。

證據：`src/siro/core/rooms.py`、`src/siro/adapters/devices.py`、
`src/siro/adapters/home_assistant.py`、`tests/integration/test_room_automation.py`、
`scripts/t29_room_demo.py`。本機沒有真 sensor、actuator 或 Home Assistant instance，故 A18 的
L3 實體設備驗收仍待執行，不能用此 simulator 結果取代。
