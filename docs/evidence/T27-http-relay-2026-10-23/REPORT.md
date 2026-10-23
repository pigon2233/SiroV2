# T27 ESP32 HTTP 接入與回讀：隔離驗證

日期：2026-10-23 Asia/Taipei。結果：**SYNTHETIC_INGRESS_VERIFIED / REAL_BOARD_PENDING / DRAFT_PR**。

## 實作

本機獨立分支加入預設關閉的 SIRO gateway `POST /v1/devices/esp32/events`：須從 loopback 連入、提供至少 32 字元的 relay token、送 `application/json` 且 body ≤4096 bytes；沿[既有事件 parser](../../../src/siro/services/devices/http_sensor.py)驗證後，由主程序持有的 DeviceRegistry／World 寫入，成功才回 `{"accepted":true}`。啟用需 `SIRO_ESP32_RELAY_TOKEN`，並設定與 payload 一致的 `SIRO_ESP32_HTTP_DEVICE_ID`；同 ID 已屬其他 adapter 時拒絕啟動，避免覆寫。`GET /v1/devices/esp32/state` 須 owner session token，僅回三個感測屬性的當前／unknown 狀態；過期值不當現況顯示。沒有設備 action／LED 控制。

新增 Windows 純標準函式庫 [8765 relay](../../../scripts/esp32_http_receiver.py)，維持 ESP32 原本的 `POST /event`；來源 IP 必須明確配置。只向 `127.0.0.1` 的 SIRO gateway 轉送一次，停用 proxy／redirect，不記錄 payload 或 token；下游 200 才向 ESP32 回 200，timeout 不重送。這不是 ESP32 自身的加密配對；LAN 來源 IP 可被誤設或冒充，不能以此代替正式 T27／A18 L3 安全驗收。

## 已執行驗證

- Python 3.14 WSL：`PYTHONPATH=src pytest -q tests/integration/test_esp32_http_gateway.py tests/integration/test_esp32_http_sensor.py tests/integration/test_esp32_sensor_telemetry.py tests/integration/test_gateway.py tests/integration/test_device_registry.py tests/integration/test_room_automation.py`：**45 passed／11.18s**。新 gateway route + SQLite World 來源／有效期／session readback、無憑證／非 loopback／超長／錯誤型別拒絕，以及真 HTTPServer relay 單次轉發／下游 503，不含實板。
- Windows `Invoke-WebRequest http://127.0.0.1:8000/health/live` 回 200；另用隔離 WSL HTTPServer 19000 驗證 Windows localhost→WSL server，WSL 記錄來源為 `127.0.0.1`。19000 測試服務已停止；**目前 8000 仍是舊運行程式，並未載入本分支。**
- Windows Python 直接執行新版 relay、未設來源 IP 時依預期拒絕啟動，沒有占用 8765。
- Ruff check／format 與新增 service、relay、test 的 targeted mypy PASS。對完整 `gateway.py` 跑 mypy 仍有兩項既有錯誤：`core/touch.py:117` untyped call、gateway 原有 `create_task` Awaitable 型別；本輪新增區段沒有 mypy 診斷。

## 未完成

使用者的 ESP32 區網來源 IP 尚待提供，因此沒有設定 allowlist、啟動 Windows 8765 relay 或更換 `C:/Users/pepepig/siro_receiver.py`；沒有重啟 8000、沒有燒錄或對實板發請求，沒有可核對的現場 World State 觀測。正式啟用要先取得 gateway 主程序與共享 `docs/DECISIONS.md` 的整合權，依[啟用說明](../../ESP32_HTTP_INGRESS.md)設定私人 token，接著做「ESP32 HTTP 200 → 同一 SIRO owner session 新鮮 state」人工驗收。GitHub 已重新登入並建立 [Issue #1](https://github.com/pigon2233/SiroV2/issues/1)／[Draft PR #4](https://github.com/pigon2233/SiroV2/pull/4)，依賴 [PR #3](https://github.com/pigon2233/SiroV2/pull/3)；本地交接見[協作紀錄](../../collaboration/T27-HTTP-EVENT-INGRESS.md)。
