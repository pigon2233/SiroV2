# T23 驗收證據

日期：2026-09-25｜結果：PASS（Linux L2）

- Rust Linux driver 提供 UTF-8 read、bounded list、atomic write、non-overwriting move；canonical root scope 拒絕越界與既有 symlink escape。
- Runtime SQLite action ledger 在 driver 前保留 action，成功後保存 readback。相同 action/args 跨重啟不重做，不同 args 回 `action_conflict`；未完成或重啟後的 `process.start` 回 `unknown_outcome`。
- process 只接受 argv，明確拒絕 shell executable；cwd 在 allowlist。run/start 建 process group；timeout kill group；stdout/stderr 寫入有 RLIMIT_FSIZE 的 regular temp files，再有界讀回；list/stop 只處理目前 driver 擁有的 process。
- Python integration 走 Core grant → Unix RPC → Rust Runtime → Linux driver → readback。A16 覆蓋 symlink、atomic write/move、持久重放、conflict、cwd、output flood、timeout、shell refusal及 start/list/stop 所有權。

最終 gate：Python 105 passed、Rust 6 passed。Windows/macOS driver 尚未實作。
