# FIX-025 — Rust child ownership 與有界輸出驗收（2026-10-16）

最終review補修：`process_group_exists` 對EPERM改回固定 `process_group_permission_denied`，沿當輪PID error路徑保留ownership／拒絕該stop，其他能力不受影響。否則leader已reap、group不可signal時，舊kill helper忽略失敗而cached wait成功，可假回stopped。

新增第11個真kernel反例：只在disposable test child安裝無特權seccomp BPF，對唯一自有negative group PID的kill回EPERM；驗group仍活、list/stop明確錯誤、ownership保持、filesystem與另一owned PID stop正常。收尾以已知positive descendant PID kill＋subreaper wait，無root、無skip、無production注入機制。原分支1 FAIL（eperm-red.log）；一行修正後最終workspace **24 PASS／0 FAIL／0 ignored**，fmt/build/clippy PASS。以下23／8FAIL為較早候選的歷史結果。

僅修改 `runtime/siro-runtime/src/linux.rs`。原版 `process.list` 已會 reap，`process.run` 已 wait；實際缺口是其他 Execute 不回收，且 list 在 leader 已退出但 descendant 仍活時丟失 group stop handle。

修復沿既有 Execute opportunistic `try_wait`：無 owned group 才移除記錄，仍有 group 則保留 stop handle。單輪 poll 錯誤以 PID 分隔；`process.list` 及該 PID stop 明確回錯，不 kill／移除未知記錄，filesystem、start、其他 owned PID stop 仍可用。沒有新 thread／trait／持久錯誤表。

原版 RLIMIT_FSIZE 與 output_limit 相同，使 129-byte write 在 128-byte cap 下回傳 returncode0 與 128-byte 前綴。修復使用 cap+1 sentinel，超量沿原 `output_limit` error 拒絕，保留正常 result shape，不新增 truncated 欄位；sentinel 有效性先於 capture 建立，讀取失敗也刪除兩個 owned capture 檔。

驗收採真 Linux owned subprocess／合成資料：退出 leader、live child、不受管 test peer、實際 ECHILD 注入、parent-exit／仍活 descendant、stdout／stderr cap+1、exact cap、zero cap、64-bit usizeMAX 與 capture cleanup。descendant fixture 僅在隔離 test child 使用 subreaper，並於任何預期回歸結果前 kill/join 自有 group；production 未新增 subreaper。

- 原 production + 全部新回歸的隔離 source-only rollback：**11 PASS／8 FAIL**，4 個非 Linux tests 因 filter 未執行，無 ignored。
- 修復 workspace：**23 PASS／0 FAIL／0 ignored**（原13 + 新10）。九個原 Linux test 函式 body 完全相同，另外四個原 tests 所在檔案未改。
- `cargo fmt --all -- --check`、`cargo test --offline --workspace`、`cargo build --offline --workspace`、`cargo clippy --offline --workspace --all-targets -- -D warnings`、scoped `git diff --check` 均 exit0。

完整命令結果見 `CHECKS.json` 與 logs。`red.log`、`rollback-red.log`、`test.log` 為較早候選；最終修復為 `final-test.log`，最終精確source-only countercheck另記於 `final-rollback-red.log`／`final-counter-green.log`。

限制：無 RPC 的閒置時間與 Health 不保證即時 reap；沒有承諾一般 subreaper/cgroup／全面 sandbox。unknown ownership 記錄需調查，不能以 PID 重用假定授權。這次未認證既有 run_process spawn／poll 故障的所有 capture 收尾分支，也未跑 remote CI／正式部署／硬體。

回退：停止新 Runtime admission 並處理仍 owned child 後，只還原上層 `before/runtime/siro-runtime/src/linux.rs`，重新 build；不回退 DB 或其他工作。已在自有 disposable Cargo workspace 僅換回 production prefix、保留全部新 tests，重現 8 個 FAIL；正式工作區保持修復版，未以 rollback 覆蓋使用者檔案。
