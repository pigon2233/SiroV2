# T27 ESP32 HTTP 事件投影驗證

日期：2026-10-23 Asia/Taipei。結果：**SYNTHETIC_INTEGRATION_VERIFIED / LIVE_INGRESS_PENDING / BLOCKED_SYNC**。

使用者提供的 `C:/Users/pepepig/siro_receiver.py` 已唯讀核對：目前只接受 `/event` JSON、印出內容並回覆 HTTP 200，不保存也不寫 SIRO World State。本輪檢查時 8765 沒有監聽程序；未重啟或替換該接收器。

在 `src/siro/services/devices/http_sensor.py` 加入現有事件格式的嚴格 parser 與投影元件。只接受預期 device ID；`light_update` 必須有有限且合法的 lux；`motion_detected`／`motion_cleared` 寫 `motion`；`button_pressed` 寫 `last_button_press_at`。拒絕超過 4 KiB、重複 JSON key、額外欄位、錯誤型別與未知事件。觀測使用**伺服器接收時間**、來源 `device:<id>:esp32_http`、20 秒有效期及 `LOCAL_ONLY` descriptor；沒有 action。PIR `motion=false` 不映射 room presence。

命令：在 WSL 專案 Python 3.14 venv 執行 `PYTHONPATH=src pytest -q tests/integration/test_esp32_http_sensor.py tests/integration/test_esp32_sensor_telemetry.py tests/integration/test_device_registry.py tests/integration/test_room_automation.py`，**20 passed／4.81s**。`ruff check`、`ruff format --check`、`mypy`（新增兩檔）及 `git diff --check` 通過。

這是合成資料直接呼叫 service 的測試；**沒有正式 HTTP route、設備認證、Windows 接收器轉發、實板同步 payload 或 SIRO 主程序中可見的現場觀測**。既有 Windows 8765 入口不能自行寫 SIRO 的獨占資料庫。正式 HTTP ingress 涉及契約與認證，須先由共享文件 owner 更新 `docs/DECISIONS.md` 與路由測試，再在 gateway 主程序內接線。不能把此結果當作 T27／T29／A18 L3 通過。GitHub 線上認領與同步目前未完成。
