# T25 驗收證據

日期：2026-09-25｜結果：PASS（Linux systemd user L2 + A17 L3；Windows/macOS unsupported）

- `SystemdUserServiceDriver` 只控制 allowlisted user units，status 回讀 ActiveState/SubState/MainPID；
  start/stop 在 readback 不符時失敗，action id 重送不重做，不同參數衝突。
- `SystemdUserUnitInstaller` 只接受簡單 `.service` 名稱；critical approval 必須精確綁定
  action ID、unit、完整內容 SHA-256 與非 pending approver。unit 以 0600 atomic replace 寫入，成功後
  daemon-reload；不提供 system package install fallback。
- 隔離 integration 以 fake systemctl 驗證 scope、idempotency、readback、approval mismatch、atomic
  install 與 reload。
- `scripts/t25_linux_a17.py` 在 GNOME Wayland 真機暫時安裝 `siro-t25-a17.service`，播放
  6 秒 PipeWire 測試音時完成 service active→HTTP ready→inactive，並在同一播放期間以可視
  Chrome 點入音訊測試頁，讀回標題 `SIRO 音訊欄位測試`。
- service stop 後 `pw-play` 仍在執行；gateway 前後均 `alive`，`/live2d/` 內容長度均為 695。
  腳本 finally 停止服務、刪除 unit、daemon-reload；驗後 systemd 回 unit not found。
- Windows/macOS 未驗，不標支援。Windows 所需 adapter 與真機 gate 見
  `docs/platforms/T25-WINDOWS.md`。

證據：`tests/integration/test_service_driver.py`、`scripts/t25_linux_a17.py`、
`docs/PLATFORM_CAPABILITIES.md`。A17 PASS。
