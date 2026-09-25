# T22 驗收證據

日期：2026-09-25｜結果：PASS（Linux L2）

- Manifest/schema/hash、SQLite registry、預設 disabled、每 job 狀態重查、input/output validation 已實作。
- 每個 job 使用 Bubblewrap process/network namespace：`--unshare-net`、只讀 Python runtime/專案 `src`/單一 skill、tmpfs `/tmp`，並使用不繼承 host secret 的最小環境。
- RLIMIT_AS/CPU、wall timeout、stdout/stderr 上限、process cancellation 與 manifest concurrency semaphore 全部強制執行。
- A15 驗證壞 manifest、disabled、echo、schema、output flood、CPU timeout、cancel、memory hog、concurrency=1、真 socket network 阻斷、host secret file 不可見、secret env 不繼承。CPU hog 期間 Core heartbeat 持續。

最終 gate：Python 105 passed、Rust 6 passed。此實作是 Linux/Bubblewrap 邊界；Windows/macOS 待各自 driver。未受信任 skill 預設 disabled。
