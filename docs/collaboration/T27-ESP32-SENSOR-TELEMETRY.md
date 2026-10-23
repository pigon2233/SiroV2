# T27 ESP32 感測遙測交接

- Owner：Codex（本任務）；2026-10-23 Asia/Taipei；狀態：LOCAL_ONLY／BLOCKED_SYNC。GitHub 未結 Issue 與 PR 在開始時均為空；GitHub 寫入 API 回 401，故**尚未完成線上認領**，此文件不是共享鎖。
- Base：`origin/main` `89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；branch：`codex/t27-esp32-sensor-telemetry`；獨立 worktree：`E:/coding/Worktrees/t27-esp32-telemetry/SiroV2`。原 `claude/cp-p02-p03-test-gaps` checkout 的四份 dirty 檔案不搬入、不修改。
- 範圍：沿既有 authenticated MQTT `state` topic，上報 PIR `motion`、BH1750 `illuminance`、按鈕 `button_down`／`button_press_count`；使用者 2026-10-23 更正實板沒有 LED，故預設 sensor-only，LED command／ACK／readback 只作明確啟用的選配。新增真 broker→World 的合成資料驗收、host 時序測試與編譯證據。PIR 未偵測到動作不代表無人，不直接映射 `presence`。修改 `firmware/esp32/**`、`tests/integration/test_esp32_sensor_telemetry.py`、本交接與本任務專屬 evidence。
- 不做：現有獨立 HTTP 接收器、正式 Gateway 啟動接線、HA、實板燒錄／設備控制。未取得共享 `docs/STATUS.md` 寫入權，不改它；PR 整合者需將本結果納入。
- 下一步：恢復 GitHub 寫入後先重查競爭認領，建立／更新 Issue 與 Draft PR；若有重疊 owner，先協調交接，不以本機較早時間搶寫。驗收結果與限制待實作後追加。

## 實作與驗證交接

- 變更：`firmware/esp32/src/main.cpp`、`include/sensor_telemetry.h`、`include/secrets.example.h`、`README.md`；新測試 `tests/integration/test_esp32_sensor_telemetry.py`；[詳細結果](../evidence/T27-sensor-telemetry-2026-10-23/REPORT.md)。`docs/STATUS.md` 不在本分支改動。
- 最終 `.python-version` 3.14.4 WSL venv：68 項 T27／World／room 相關回歸 **PASS／33.13s**，新測試含真 broker＋合成 state；Ruff、format、mypy、diff PASS。PlatformIO Core 6.1.19／pinned esp32dev 最終編譯 SUCCESS；沒有刷板。3.12 舊 broker/LWT 個案曾逾時，3.14 獨立重跑 2 PASS，失敗保留在報告。
- 限制：使用者提供 ESP32-S3 N16R8；本輪以先前草稿的 GPIO 4／5／8／9 作編譯設定，仍需核對實際接線與模組標示。目前設備仍跑獨立 HTTP 草稿，未切換 MQTT；正式 SIRO Gateway 尚未訂閱並投影此 MQTT state。PIR `motion=false` 不等於無人，不能直接作房間 presence。沒有 LED，故 T27 actuator 真板與 A18 L3 仍 HARDWARE_PENDING。超音波感測器尚未裝，暫不納入。
- 同步：本地先前 commit `7b5a803`，S3 無 LED 更正 commit `9f1d3b9`。GitHub API 寫入先前回 401；本輪 `git push --dry-run` 在未完成登入時等待憑證，取消後以無互動模式重試，回覆 `Cannot prompt because user interactivity has been disabled`。**未 push、未開 Issue／Draft PR、未完成線上認領**。恢復 GitHub 登入後須先重查競爭認領與遠端基線，不由此文件推定共享 STATUS owner。
