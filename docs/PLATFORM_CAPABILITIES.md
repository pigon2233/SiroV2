# 平台能力表

更新：2026-09-25

| 能力 | Linux | Windows | macOS | 邊界 |
|---|---:|---:|---:|---|
| filesystem.read/list | T23 已驗證 | 待實作 | 待實作 | canonical path 必須位於 grant roots |
| filesystem.write/move | T23 已驗證 | 待實作 | 待實作 | atomic replace、action ledger、不覆寫 move target |
| process.list/start/stop | T23 已驗證 | 待實作 | 待實作 | 只停止 driver 所有的 process group |
| process.run | T23 已驗證 | 待實作 | 待實作 | argv-only、cwd allowlist、timeout/cancel/output limit |
| shell language | 未開放 | 未開放 | 未開放 | 需獨立高權限 capability，不把模型文字拼成 shell |
| browser navigate/read | T24 Chrome 已驗證 | 未驗證 | 未驗證 | 只允許 grant origins；redirect/subresource 在送出前檢查 |
| browser fill/click/key/pointer | T24 Chrome 已驗證 | 未驗證 | 未驗證 | 每次動作驗證 screen version；畫面變更後須重新觀察 |
| browser screenshot | T24 Chrome 已驗證 | 未驗證 | 未驗證 | 只擷取已授權 browser page；影像預設不持久保存 |
| local pixel screen analysis | T24 已驗證 | 未驗證 | 未驗證 | 只回報尺寸、亮度、粗略色彩、來源與信心，不宣稱語意理解 |
| cloud VisionModel | 無可用 Groq vision model | 未驗證 | 未驗證 | port 已定義；沒有模型時明示 unavailable |
| arbitrary desktop window/key/pointer | Wayland unsupported | 未實作 | 未實作 | DOM 控制成功不代表任意桌面程式可控 |
| user service status/start/stop | T25 systemd user 已驗證 | 未實作 | 未實作 | unit allowlist、action ledger、狀態 readback |
| user service unit install | T25 已驗證 | 未實作 | 未實作 | critical；action/unit/content SHA-256/approver 必須完全相符 |
| system package install | unsupported | 未實作 | 未實作 | 沒有安全 adapter；不得以 process.run 迴避 critical approval |

T23 的 Linux driver 是 Runtime 之後的受限執行元件；實際呼叫時仍需 T21 grant 驗簽、capability、scope 和 arguments hash 通過。T24 browser driver 同樣只接受明列 origin，且不把 DOM 權限擴張成作業系統桌面權限。
