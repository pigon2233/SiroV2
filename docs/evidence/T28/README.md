# T28 驗收證據

日期：2026-09-26｜結果：PASS（official-protocol mock integration）；REAL HOME ASSISTANT PENDING

- `HomeAssistantAdapter` 使用官方 REST `Authorization: Bearer` 、`GET /api/states`、
  `GET /api/states/<entity_id>` 與 `POST /api/services/light/turn_on|turn_off`。服務 POST
  回 200 後仍必須 GET readback；狀態仍是 `off` 會回報
  `state_unchanged`，不宣告開燈成功。
- 官方 WebSocket `auth_required → auth → auth_ok` 和
  `subscribe_events(state_changed)` 以 loopback 真 WebSocket server 驗證；初始 REST
  snapshot 與后續 event 都投影到 T26 registry/world model。
- `config/home-assistant.example.json` 只指定 `SIRO_HA_TOKEN` 的環境變數名稱；
  loader 拒絕將 token 寫入設定檔，`SecretStr` 不會出現在 config repr。
- 測試驗證 action ID 庫存與參數衝突拒絕、撤銷憑證回報
  `auth_revoked`、`unavailable` 裝置回報 `unavailable`。

官方依據：[Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)、
[Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)。

證據：`src/siro/adapters/home_assistant.py`、
`config/home-assistant.example.json`、`tests/integration/test_home_assistant.py`。此主機未提供
Home Assistant instance 或 device/token，因此不宣稱已完成真實 HA 或 T29 的硬體閉環。
