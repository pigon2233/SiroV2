# T26 驗收證據

日期：2026-09-25｜結果：PASS（SQLite integration + simulators）

- `DeviceDescriptor` 固定 device/adapter/location、typed readable properties、canonical actions、events、
  availability TTL 與 privacy；schema 匯出至 `schemas/devices/descriptor.v1.schema.json` 並由
  `scripts/export_schemas --check` 防止 stale。
- `SQLiteDeviceRepository` 使用既有 `devices` 與 `entity_edges`，descriptor upsert 同步
  `located_in` 房間 edge；availability/last_seen 與 descriptor 分開保存。
- `DeviceRegistry` 依 canonical action 找設備，不依品牌寫 Core 分支。測試加入 brand A/B 虛擬燈，
  兩者均透過 `light.set` 發現；command ID 重送同 desired state 不重做，改 desired state 拒絕。
- availability 由 last_seen＋TTL 推導；online 超時成 stale。presence 只採用位於該房間、online、
  未過期且型別為 boolean 的觀測。無 location sensor 即使回 true 也不能推斷人在房間；唯一有效
  sensor 過期後結果回 unknown。
- simulator 包含 light、presence、temperature。camera 共用 `camera.capture` capability，但 owner
  未 enable 時拒絕；enable 後每次顯式呼叫才產生 frame，沒有永久 capture loop。

證據：`tests/integration/test_device_registry.py`、`src/siro/core/devices.py`、
`src/siro/persistence/devices.py`、`src/siro/adapters/devices.py`。
