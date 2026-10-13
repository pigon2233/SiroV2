# FIX-011 independent implementation review

日期：2026-10-11（Asia/Taipei）。結論：**目前凍結的 D45 trusted-local lifecycle 修復，無剩餘已確認的 scoped blocker**。這是 source／合成 runtime 的獨立審查；完整回歸、static checks 與精確 rollback 仍由本卡主執行者另記，不能用這份 review 代替。

本輪沒有修改 production、tests、roadmap 或全域文件；僅寫 owned evidence。所有 probe 使用 temporary 合成 package／SQLite／marker，不讀私人資料、模型或 live 8026，不執行產品 registry activation。

## Source binding

精確五檔 source/test hashes 與 unchanged AST／baseline comparison 保存在 [`independent-source-binding.json`](independent-source-binding.json)。本 review 指向以下凍結內容：

| File | SHA-256 |
|---|---|
| `src/siro/adapters/skill_worker.py` | `78e740a0ecb2d61f6f452a63b4c7d1becb88d353095319a2bda2bbb2e75b0ec5` |
| `src/siro/skill_worker.py` | `3d8cec992b62882815ff28686e21c24b6b461793db3815820786ee404166cf86` |
| `src/siro/services/tools/execution.py` | `f8bcf7e3021c83d7e6c761803a9039f7141ec439be71131b5e1c0dad5c5b6025` |
| `src/siro/adapters/process_execution.py` | `340dfc09933d804e7b25395f5a8a1a19f5a93c40d50012931b24614755cf19a8` |
| `tests/integration/test_skill_worker_lifecycle.py` | `db745170e1bc98ae8a115c8522e0bef050c8d4250eb7e6b4a350df9ebd9702b5` |

Package capture／frozen snapshot 與 per-skill concurrency／Dispatcher 8-slot admission 的 AST 與本卡 before snapshot 相同。core skills、persistence registry、D44 candidate service、D43 verifier／runner、Gateway、ToolCatalog／ToolOrchestrator 的 source hash 與本卡 baseline 相同。Dispatcher 最末 cleanup 增加 primary typed error preservation，沒有改 full identity checks 或批准判斷。

## Findings found and locally resolved

| Finding | Actual evidence | Root cause / follow-up |
|---|---|---|
| 新 worker 將非法 UTF-8 JSON 修成成功結果 | [`independent-utf8-probe.json`](independent-utf8-probe.json)：actual temporary worker 寫 `{"text":"\xff"}`，舊新 helper tolerant decode 曾使結果變成 `{"text":"�"}` | Worker 現以 shared owner 的 `stdout_errors="strict"` 讀 stdout；其他 service callers 維持 tolerant default。[`independent-local-fix-followup.json`](independent-local-fix-followup.json) 實測非法 bytes 變為 SkillExecutionError，合法 literal U+FFFD 原樣成功，不能 blanket reject replacement character |
| facade 曾刪掉實際 Gateway caller 使用的 private cleanup 入口 | [`independent-compatibility-probe.json`](independent-compatibility-probe.json)：`gateway.application_tool` 的 `_protected_cleanup` import 曾實際 ImportError | 保留原 `(process, readers)` wrapper，向下共用 owner 與 service signal hook。follow-up import 已成功，Gateway source 不需改，也沒有第二套 executor |
| worker process cleanup failure 曾被 request cleanup 的 late cancel 蓋掉 | `worker-after.log` 的 `test_process_cleanup_failure_survives_late_request_cleanup_cancel` 曾 FAIL，18 PASS／1 FAIL | WorkerSupervisor finally join request cleanup 時保留 primary ExecutionCleanupError；正常完成遇 late cancel 仍取消，不偽成功。最終 `worker-final.log` 對應 case PASS |
| 同樣的 typed failure 可再被外層 Dispatcher snapshot cleanup 蓋掉 | [`independent-dispatcher-error-probe.json`](independent-dispatcher-error-probe.json)：actual Dispatcher＋temporary registry，stub worker raises typed cleanup failure，兩次 cancel during snapshot cleanup 曾只回 CancelledError | 此模式在 D40 before 已存在；在原 scoped skill_worker 檔做相同 finally 局部修復。[`independent-dispatcher-error-after.json`](independent-dispatcher-error-after.json) 實测保持 ExecutionCleanupError，snapshot_removed=true；不改 registry／identity 語意 |

Supplemental RED tests 保存在 `worker-utf8-before.log`（3 FAILED／1 PASS）及 `dispatcher-error-before.log`（1 FAILED／23 deselected），不是全部舊來源 case 的 RED count；原 `worker-before.log` 仍為 5 FAILED／9 deselected／0.51s。

## Ownership and compatibility assessment

- Worker request 是獨立 owned workspace 的有界 JSON，offloop serialize／write／remove；read-only mount，不加入 package hash，不接受 caller 指定路徑。NaN／Infinity 與超 64KiB request 在 spawn 前拒絕。legacy stdin 有界入口保留。
- 只有 adapter bounded process helper 建立 session／PGID；worker 沒有反向 import services。bwrap 去除重複 session 並加入 PID namespace，原 source/runtime mounts、network denial 與 trusted-local resource/concurrency 契約保留。
- Shared stdout/stderr 一直 drain，到 collective manifest deadline／context cancellation 會走 owned TERM/KILL；超量、truncation、invalid UTF-8／JSON／object 都不能作成功結果。manifest 毫秒精度保留。
- request preparation、spawn、collect、最後 cleanup 的取消都有 join；late／repeated cancel 不拋下自己建立的資源。primary process cleanup error 在 request 與 outer snapshot cleanup 層均保留，正常 late cancellation 不回成功。
- 原 service errors/context 仍與 adapter 是相同 class identity；service `_signal_owned_group` seam 和實際 Gateway `_protected_cleanup` caller 可向下使用原 owner。沒有直接 product execution／approval／install endpoint。
- [`independent-spawn-flood-probe.json`](independent-spawn-flood-probe.json) 額外將實際子程序的 stdout 塞至 pipe paused，再在 delayed spawn return 時取消：0.251s 回 CancelledError、direct returncode=-15。此合併窗口沒有重現新 process cleanup failure；沒有將 negative control 說成新的漏洞。

已讀 final owned test log：[`worker-final.log`](worker-final.log) **24 PASS／3.41s**。這包含 real trusted bwrap、namespace descendant／unrelated canary、input/output limits、取消與 cleanup，以及 synthetic refusal seams；mock 與真 OS case 不互相取代。未在本 review 重跑全 repository 或任何真模型。

## Gates that remain

FIX-011 **不是 strict generated-skill sandbox 驗收**。舊 trusted worker 保留 `/usr`、venv/source、dev/proc 與可 fork／exec 的行為；RLIMIT_AS／CPU 是 process 限制，CPU soft limit 仍可提高至既有 hard limit。PID cleanup 修復不等於不可逃的 mount／syscall／credential／aggregate memory boundary。

其他 OS、delegated cgroup aggregate SLO、blocked host IO cleanup SLO、長期 semaphore retention、arbitrary generated code、security review／explicit package-bound approval／install／enable／revoke／catalog 接入仍未驗。RI-004 整體保持 PARTIAL，D44 待審準備切片維持已驗成果；RI-005 的 release gates 不變。不得以本 review 或 24 tests 解除這些 gate。

如果上述五檔再次變更，這份凍結結論需要針對差異重查；本卡其他範圍失敗由完整回歸另判，不為通過此 review 放寬需求。
