# T27 ESP32 感測遙測交接

- Owner：Codex（本任務）；2026-10-23 Asia/Taipei；目前狀態：**DRAFT_PR／HARDWARE_PENDING**。[Issue #2](https://github.com/pigon2233/SiroV2/issues/2) 已線上認領，[Draft PR #3](https://github.com/pigon2233/SiroV2/pull/3) 已推送。開始實作時 GitHub 寫入不可用，因此下文保留當時的 LOCAL_ONLY 經過；本文件本身不是共享鎖。
- Base：`origin/main` `89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；branch：`codex/t27-esp32-sensor-telemetry`；獨立 worktree：`E:/coding/Worktrees/t27-esp32-telemetry/SiroV2`。原 `claude/cp-p02-p03-test-gaps` checkout 的四份 dirty 檔案不搬入、不修改。
- 範圍：沿既有 authenticated MQTT `state` topic，上報 PIR `motion`、BH1750 `illuminance`、按鈕 `button_down`／`button_press_count`；使用者 2026-10-23 更正實板沒有 LED，故預設 sensor-only，LED command／ACK／readback 只作明確啟用的選配。新增真 broker→World 的合成資料驗收、host 時序測試與編譯證據。PIR 未偵測到動作不代表無人，不直接映射 `presence`。修改 `firmware/esp32/**`、`tests/integration/test_esp32_sensor_telemetry.py`、本交接與本任務專屬 evidence。
- 不做：現有獨立 HTTP 接收器、正式 Gateway 啟動接線、HA、實板燒錄／設備控制。未取得共享 `docs/STATUS.md` 寫入權，不改它；PR 整合者需將本結果納入。
- 下一步：PR 審查並由整合者更新共享 `docs/STATUS.md`；核對實板模組、腳位與 MQTT 配置後才可燒錄驗收。若有重疊 owner，先協調交接。

## 實作與驗證交接

- 變更：`firmware/esp32/src/main.cpp`、`include/sensor_telemetry.h`、`include/secrets.example.h`、`README.md`；新測試 `tests/integration/test_esp32_sensor_telemetry.py`；[詳細結果](../evidence/T27-sensor-telemetry-2026-10-23/REPORT.md)。`docs/STATUS.md` 不在本分支改動。
- 最終 `.python-version` 3.14.4 WSL venv：68 項 T27／World／room 相關回歸 **PASS／33.13s**，新測試含真 broker＋合成 state；Ruff、format、mypy、diff PASS。PlatformIO Core 6.1.19／pinned esp32dev 最終編譯 SUCCESS；沒有刷板。3.12 舊 broker/LWT 個案曾逾時，3.14 獨立重跑 2 PASS，失敗保留在報告。
- 限制：使用者提供 ESP32-S3 N16R8；本輪以先前草稿的 GPIO 4／5／8／9 作編譯設定，仍需核對實際接線與模組標示。目前設備仍跑獨立 HTTP 草稿，未切換 MQTT；正式 SIRO Gateway 尚未訂閱並投影此 MQTT state。PIR `motion=false` 不等於無人，不能直接作房間 presence。沒有 LED，故 T27 actuator 真板與 A18 L3 仍 HARDWARE_PENDING。超音波感測器尚未裝，暫不納入。
- 同步：先前 commits `7b5a803`、`9f1d3b9`、`a5f79e5` 已推送到 `origin/codex/t27-esp32-sensor-telemetry`；Issue #2／Draft PR #3 已建立。先前 GitHub 401 與未登入失敗屬歷史過程。沒有合併、部署或更新共享 `docs/STATUS.md`；PR 整合者需核對並更新。
