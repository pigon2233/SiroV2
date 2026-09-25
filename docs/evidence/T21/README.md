# T21 驗收證據

日期：2026-09-25｜結果：PASS（L1 + cross-process L2）

- Rust 1.97.1、rustfmt、Clippy 與 Cargo lock 已固定。
- Core 的 default-deny ALLOW/DENY/ASK policy 會把完整 arguments 綁入一次性 approval/grant；更換參數或重放 approval 會拒絕。
- Runtime 使用自己的系統時鐘，不接受 client timestamp。HMAC verifier 拒絕偽造、過期、撤銷、耗盡、capability/scope/arguments mismatch。
- 0600 Unix socket、64 KiB 上限、grant/revocation/audit/action SQLite state 位於 Rust Runtime。跨重啟撤銷與 use count 保留；state/audit 寫入失敗會 fail closed。
- action ledger 回傳持久 readback；相同 action 不重做，不同 args 為 `action_conflict`，未完成狀態為 `unknown_outcome`。
- Python integration 由 Core grant 經 Unix RPC 執行真 Rust Linux driver，再查核 SQLite audit。Runtime 離線時工具拒絕，文字 Core 仍可運作。

最終 `scripts/check`：Python 105 passed、5 個明示 opt-in skips；Rust 6 passed；ruff/mypy/Cargo fmt/Clippy/schema/secret scan 全通過。A14 覆蓋所有上述拒絕與無副作用條件。
