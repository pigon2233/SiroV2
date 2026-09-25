# 平台能力表

更新：2026-09-25

| 能力 | Linux | Windows | macOS | 邊界 |
|---|---:|---:|---:|---|
| filesystem.read/list | T23 已驗證 | 待實作 | 待實作 | canonical path 必須位於 grant roots |
| filesystem.write/move | T23 已驗證 | 待實作 | 待實作 | atomic replace、action ledger、不覆寫 move target |
| process.list/start/stop | T23 已驗證 | 待實作 | 待實作 | 只停止 driver 所有的 process group |
| process.run | T23 已驗證 | 待實作 | 待實作 | argv-only、cwd allowlist、timeout/cancel/output limit |
| shell language | 未開放 | 未開放 | 未開放 | 需獨立高權限 capability，不把模型文字拼成 shell |

T23 的 Linux driver 是 Runtime 之後的受限執行元件；實際呼叫時仍需 T21 grant 驗簽、capability、scope 和 arguments hash 通過。
