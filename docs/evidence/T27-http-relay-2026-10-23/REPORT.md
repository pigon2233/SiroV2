# T27 ESP32 HTTP 接入與回讀：隔離驗證

日期：2026-10-23 Asia/Taipei。結果：**REAL_BOARD_HTTP_LIGHT_TO_ISOLATED_WORLD_VERIFIED / PRODUCT_DEPLOY_PENDING / DRAFT_PR**。

## 實作

本機獨立分支加入預設關閉的 SIRO gateway `POST /v1/devices/esp32/events`：須從 loopback 連入、提供至少 32 字元的 relay token、送 `application/json` 且 body ≤4096 bytes；沿[既有事件 parser](../../../src/siro/services/devices/http_sensor.py)驗證後，由主程序持有的 DeviceRegistry／World 寫入，成功才回 `{"accepted":true}`。啟用需 `SIRO_ESP32_RELAY_TOKEN`，並設定與 payload 一致的 `SIRO_ESP32_HTTP_DEVICE_ID`；同 ID 已屬其他 adapter 時拒絕啟動，避免覆寫。`GET /v1/devices/esp32/state` 須 owner session token，僅回三個感測屬性的當前／unknown 狀態；過期值不當現況顯示。沒有設備 action／LED 控制。

新增 Windows 純標準函式庫 [8765 relay](../../../scripts/esp32_http_receiver.py)，維持 ESP32 原本的 `POST /event`；來源 IP 必須明確配置。只向 `127.0.0.1` 的 SIRO gateway 轉送一次，停用 proxy／redirect，不記錄 payload 或 token；下游 200 才向 ESP32 回 200，timeout 不重送。這不是 ESP32 自身的加密配對；LAN 來源 IP 可被誤設或冒充，不能以此代替正式 T27／A18 L3 安全驗收。

## 已執行驗證

- Python 3.14 WSL：`PYTHONPATH=src pytest -q tests/integration/test_esp32_http_gateway.py tests/integration/test_esp32_http_sensor.py tests/integration/test_esp32_sensor_telemetry.py tests/integration/test_gateway.py tests/integration/test_device_registry.py tests/integration/test_room_automation.py`：**45 passed／11.18s**。新 gateway route + SQLite World 來源／有效期／session readback、無憑證／非 loopback／超長／錯誤型別拒絕，以及真 HTTPServer relay 單次轉發／下游 503，不含實板。
- Windows `Invoke-WebRequest http://127.0.0.1:8000/health/live` 回 200；另用隔離 WSL HTTPServer 19000 驗證 Windows localhost→WSL server，WSL 記錄來源為 `127.0.0.1`。19000 測試服務已停止；**目前 8000 仍是舊運行程式，並未載入本分支。**
- Windows Python 直接執行新版 relay、未設來源 IP 時依預期拒絕啟動，沒有占用 8765。
- Ruff check／format 與新增 service、relay、test 的 targeted mypy PASS。對完整 `gateway.py` 跑 mypy 仍有兩項既有錯誤：`core/touch.py:117` untyped call、gateway 原有 `create_task` Awaitable 型別；本輪新增區段沒有 mypy 診斷。

## 未完成

### 真板對隔離 SIRO 的短暫閉環

2026-10-23 15:20 Asia/Taipei，短暫啟動使用者既有 `C:/Users/pepepig/siro_receiver.py`，實際收到來自 `192.168.1.182`／device `siro-node-01` 的三筆 `light_update`：239.2、236.7、235.8 lx，接收器分別記錄 HTTP 200。停掉舊 receiver 後，在 WSL `127.0.0.1:19001` 啟動**本分支程式組成的隔離 gateway**，資料庫位於臨時 `/tmp`；Windows 新 relay 限定來源 `192.168.1.182`、目的 port 19001，使用短期測試 token。透過該 gateway 的 owner session token 呼叫 `GET /v1/devices/esp32/state`，讀到 `illuminance: known`、235.0 lx、`observed_at: 2026-10-23T15:22:33.505166+08:00`、`source_id: device:siro-node-01:esp32_http`。這是**實板 HTTP 光度資料到隔離 World State 的證據**；不是正在運作的 8000 產品 DB。沒有讀到 PIR 或按鈕邊緣，也未取得新 relay 這次回給 ESP32 的序列埠狀態碼。測試後兩個臨時服務都已停止，8765／19001 無 listener，臨時 DB 已刪除；不保存原始 sensor log 或測試 token。

正式 8000 仍跑另一工作分支，沒有重啟、合併、部署、燒錄或替換 `C:/Users/pepepig/siro_receiver.py`。ESP32 的 IP 目前觀察為 `192.168.1.182`，正式設定前須再核對 DHCP 是否變更。正式啟用要先取得 gateway 主程序與共享 `docs/DECISIONS.md` 的整合權，依[啟用說明](../../ESP32_HTTP_INGRESS.md)設定**新產生的私人 token**，接著做正式 owner session 的新鮮 state／PIR／按鈕人工驗收。GitHub 已重新登入並建立 [Issue #1](https://github.com/pigon2233/SiroV2/issues/1)／[Draft PR #4](https://github.com/pigon2233/SiroV2/pull/4)，依賴 [PR #3](https://github.com/pigon2233/SiroV2/pull/3)；本地交接見[協作紀錄](../../collaboration/T27-HTTP-EVENT-INGRESS.md)。

遠端驗證追加：PR #4 的 `python` job 同樣於 `ruff format --check` 失敗，指出 `design/companion/blender-style-study/0.1.0/{build_siro,inspect_glb,inspect_preview}.py` 與 `tests/integration/test_vrm_renderer.py`。四檔與 `origin/main` 比較無差異，也不在 PR #3／#4 修改檔清單中；CI 因此尚未執行後續完整驗收，不能宣稱通過。保留 Draft，不在本任務搶寫其他 owner 的檔案。
