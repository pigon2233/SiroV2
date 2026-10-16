# D61 急修清單重驗 — 2026-10-16

使用者再次要求 MQTT、模型串流、SQLite、Python sandbox 與 Rust 子程序修復。
本輪核對已追蹤的 `940bdb7`，沒有再修改 production 或重做已解問題。

## 核對與實測

- MQTT：只有 wire `applied` 接受；未知 ID 回 None；拒絕進 FAILED、後續 ACK 不復活。
  terminal 狀態先保留供 caller 查詢，`issue`／顯式 `prune` 回收；預設容量1024，滿 active 拒新。
  不用立即刪除破壞 `state()` 相容性，也不將 simulator 的 `accepted` 當 wire 成功。
- 模型：HTTP／Ollama／OpenAI SSE 已以固定安全 `ProviderResponseInvalid` 處理 JSON／Unicode 錯誤，
  Ollama error envelope 不再假完成。失敗、取消與下一輪恢復均有既有反例。
- SQLite：原 WAL／NORMAL／busy_timeout5000 保持；五條路徑及配置失敗已明確關閉連線。
- Python sandbox：原認證環境是 Linux x86_64／system3.14；缺件時 patch verification 回
  `unsupported_platform`／`unsupported_sandbox`，strict worker 拋 `SkillExecutionError`，不降級至 host。
  `sys.executable` 不能單獨保證 loader／stdlib／seccomp 與掛載 allowlist 相容，因此不依該建議放寬邊界。
  尚未認證其他系統／版本；缺件原因在產品端只顯示通用錯誤，是診斷體驗 technical debt。
- Rust：既有 Execute 路徑回收已退出 child，仍活 group 保留可停止所有權；EPERM 不假 stopped，
  超量輸出沿原 `output_limit` 拒絕。沒有新增背景清理 owner 或 RPC 欄位。

實際重跑：

```text
.venv/bin/python -m pytest -q \
  tests/integration/test_mqtt_tracker_resilience.py \
  tests/integration/test_mqtt_time_formats.py \
  tests/integration/test_esp32_mqtt_probe.py \
  tests/integration/test_sqlite_connection_cleanup.py \
  tests/integration/test_model_protocol_recovery.py
111 passed in 19.55s, exit 0
```

MQTT peer 為合成、Broker／client 為真實 loopback；模型 HTTP 回應為合成，SQLite 為真暫存資料庫。
前輪完整候選 **2129 Python PASS／5原opt-in SKIP、24 Rust PASS、整條 scripts/check EXIT0**
保留於 [REPORT](REPORT.md)。本輪先確認323份 source/test/build hash 一致；之後其他工作修改
UI／啟動檔，不能將本卡 PASS 套用到並行工作。本卡來源的逐檔核對見 `CURRENT_HEAD_RECHECK.json`。

ESP32 既有 pinned 設定的真交叉編譯另已 PASS；[編譯證據](../T27-firmware-build-2026-10-16/REPORT.md)。
沒有讀真帳密、燒錄、操作 GPIO 或宣稱目視 LED／真 NTP 通過。

## Git 交付界線

續作時發現本機已有新的 `940bdb7` 提交，含458個 changed files；不是本輪根代理建立。
遠端 main 仍為 `215aaa9`。該提交除本卡外，另納入大量先前 untracked 驗證快照，全部保留。

獨立 owned clean clone 跑原 scanner／strict gate，**EXIT1**：1332個未允許項，
1331個為 JSON 摘要／指紋，1個為獨立測試的合成 api_key literal；原六個公開 pins 正常允許。
另掃新增文字／強 credential 格式，未識別出真憑證；40張舊圖片未做視覺隱私驗收，
不能將文字掃描稱為完整公開範圍認證。乾淨 clone 已移除，沒有推送或改檢查門檻。

此為 **BLOCKED_BY_DELIVERY_REVIEW**，不將上述文件掃描阻擋誤列為 MQTT／模型／SQLite／Rust 回歸。
後續需單獨收斂使用者新提交的公開範圍／指紋證據處理；不刪快照、不重寫該提交、不全面允許雜湊。
FIX-022–025維持 LOCAL_VERIFIED；remote CI、正式部署與實板驗收仍各自未驗。
