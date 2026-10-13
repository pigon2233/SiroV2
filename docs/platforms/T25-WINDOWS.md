# T25 Windows 子卡

狀態：UNSUPPORTED / REAL-MACHINE PENDING

Linux T25 的結果不外推到 Windows。Windows adapter 後續至少需要：

- 以 Windows Service Control Manager API 查詢、啟動與停止 allowlisted service；
- install/change service 列為 critical，approval 綁 action、service、binary path、arguments 與 hash；
- 只控制由 SIRO 建立或 owner 明列的 service，不以系統管理員 shell 字串代替 API；
- UI Automation 與 browser automation 分開宣告，不把 DOM 測試當成 Win32/UIA 支援；
- Windows 11 真機完成 A17：可取消 UI 動作、服務 active/stopped readback、音訊不中斷、失敗服務
  不阻斷 presentation，清理測試服務；
- 補 ACL、路徑 quoting、service account、UAC、reboot pending 與 rollback 測試。

在這些條件完成前，能力矩陣必須回 `unsupported`，不能自動 fallback 到 PowerShell 或 shell。
