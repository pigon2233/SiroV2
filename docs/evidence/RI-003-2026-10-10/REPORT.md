# RI-003 — Linux single-process candidate verification

日期：2026-10-10。決策／契約：D43。RI-003 整體 **PARTIAL**；本機 Linux x86_64、system CPython 3.14、`python-unittest-single` 明確 owner 切片 **VERIFIED**。不可信候選現在有實際 OS 隔離的驗證入口；其他 profiles、技能啟用與發布不因本卡通過而放行。

## Delivered behavior and scope

新增明確 owner CLI：

```sh
.venv/bin/siro verify-patch PROPOSAL_JSON --project-root ROOT --profile python-unittest-single
```

等效入口是 `.venv/bin/python -m siro.cli verify-patch ...`，實際 CLI 測試使用後者。`PROPOSAL_JSON` 使用既有 `PatchProposal` 三欄：UUID `proposal_id`、有界 text `unified_diff`、`created_at`。`ROOT` 必須是 owner 選定的 canonical source 目錄，改動只允許可見 `src/**/*.py`／`tests/**/*.py`。此 profile 跑標準函式庫 synchronous unittest，不安裝依賴，也不接受任意命令。至少一個測試成功、輸出未截斷才能回 `passed`。

Async caller：`verify_isolated_patch(project_root, proposal, profile="python-unittest-single", context=None)`。Core 只新增 pure `preflight_patch`，沿用 FIX-008 parser／protected paths。舊 trusted `PatchVerifier` API 保持相容，仍只供可信 developer checks；不得拿 copy/cwd 當 OS isolation。`VerificationReport` 五欄不變。

只改兩個既有 production 檔：`src/siro/core/evolution.py`、`src/siro/cli.py`。新增 service backend／trusted runner 兩檔與 integration tests 兩檔。沒有修改 Core permission/config policy、模型／語音／renderer／Gateway、skill registry、release manager、資料 schema 或依賴。不是 runtime model tool，也沒有自動生成／啟用／部署 caller。

CLI exit：passed 0；已解析的 verification rejection 1；非法 JSON/input 2；中止並清理後 130。Cleanup failure 保留 `ExecutionCleanupError`，不假稱 workspace 已移除。

## Verified isolation boundary

| Boundary | Implemented behavior | Actual verification |
|---|---|---|
| Source and privacy | No-follow fd traversal，只捕捉可見普通單 link `.py` bytes；拒絕 alias／cross-device／churn；最多 512 files、1,024 entries、32 levels、每檔 4MiB／總量 16MiB。git apply 後重驗同一上限 | Synthetic `.env`／private canary 不複製、不開啟；symlink/hardlink/root alias、檔數與大小、patch 擴量拒絕；host source unchanged |
| Candidate execution | 新 user/PID/net/IPC/UTS 等 namespace；cap drop、disable userns；只 mount projected source、固定 system Python/stdlib/libs 與候選外 trusted runner | 真 bubblewrap namespace 內惡意 import 讀／寫外部、network、fork/exec／session escape 均拒絕 |
| Immutable restrictions | `-I -S -B`，先載 trusted stdlib，no_new_privs、hard rlimits、不可撤銷 seccomp，完成後才加 candidate import paths | namespace 內缺 seccomp 的 fixture 不執行候選；fork/clone3、exec/socket、raise limits、memfd/shm/keyring 與 IPC creation 負向測試 |
| Storage and resources | Candidate/trusted/root/proc/dev readonly，唯一 scratch `/tmp` file-data size 8MiB；AS 256MiB、CPU 5s、FSIZE 1MiB、NOFILE 64、CORE 0；pipeline process deadline 10s、retained raw stdout+stderr 64KiB | 真 allocation／CPU／file／scratch／output flood fixtures 拒絕或 failed_checks；truncated 不能 passed |
| Ownership and cancellation | 重用既有 bounded process owner／PGID cleanup；唯一 owner 建 session，candidate setsid/setpgid 被拒；prep/validation/disk cleanup 的 offloop task 取消後 join，再傳遞取消 | Actual API repeated cancellation、external deadline；actual CLI 單／雙 SIGINT、完整 owned descendant PID tree 消失、workspace 移除；late cleanup cancellation 不回 passed |
| Fail closed | 不支援平台／缺 runtime/bwrap/git/libs/filter → unsupported；profile/path/input/policy 不符 → rejected；无 host fallback | 入口 rejection／zero executor fixtures；真 namespace filter failure fixture；original trusted verifier 63 cases 保留 |

本機版本：Python／system CPython **3.14.4**，bubblewrap **0.11.1**，`libseccomp2:amd64` **2.6.0-2ubuntu5**。`pkg-config` 未提供 libseccomp metadata；版本來自實際 package inventory，不把該失敗命令列 PASS。沒有安装或更新 OS 套件。

## Acceptance results on final source

| Executed check | Result | Evidence |
|---|---|---|
| Final 48 new cases against exact pre-card dirty source, isolated source-only projection | **48 failed / 2.09s**；原版本沒有新入口／相應契約 | `complete-tests-before-final.json`／`.log`，不是 48 個 production 事故 |
| New isolated API/CLI cases + original patch/path regressions | **111 passed / 11.50s** | `tests-after-final.log`；48 new + 63 existing，不另外加到 full 數量 |
| `.venv/bin/pytest -q -m 'not real_provider'` | **1,039 passed / 5 deselected / 3 existing warnings / 127.78s** | `full-suite-final.log`，沒有新 skip；991 pre-card baseline + 48 new |
| Ruff format / lint / mypy / schema / diff check | **PASS**；230 formatted files、220 typed source files | `checks.json`，各命令 exit 0。首次直接用 system Python 執行 schema script 缺 installed package；改用既有 `.venv/bin/python` 後 PASS，未改 schema |
| Six-file source / owned evidence secret scans, network verification disabled | Source **0 findings**；evidence **254 recorded SHA/commit false positives**, unresolved **0** | `secrets-source.json`／`secrets-evidence.json`／`secrets-review.json`；每個 evidence finding 精確對上命名 digest 欄位與 detector hash，未隱藏 raw 結果；沒有讀 private config |
| Existing dirty source preservation | **PASS**；231 existing source/script/test/lock hashes 中僅兩個預期 source 改變；四檔新增 | `preservation.json`，精確 final SHA |
| Six-file patch reverse/check/reapply in temporary tree | **PASS**；舊兩檔 SHA 完全恢復、新四檔移除、重套後 SHA 完全相同 | `repair.patch`、`rollback.json`、`verify_source.py` |
| Independent read-only final source audit | **No remaining confirmed scoped blocker**；兩個 finding 先 RED 再局部修正，follow-up 確認 | `source-review.md`；執行證據由 root 負責 |

`tests-before.log` 為初始 34-case RED；`tests-after-first.log` 的 32 PASS／2 FAIL 是 fixture exception type／mock keyword 不符，修正 fixture，沒有放寬驗收。1033／1034／1037 等中間 full logs 保留為歷史，不是 final source 驗收。

## Defects found while verifying this candidate

這些缺陷都在未啟用的新候選切片找到；沒有證據稱為正式產品事故或舊 RT regression。

| Confirmed root cause | Retained RED evidence | Small local correction |
|---|---|---|
| Kernel memfd allocation 未被限制、patch 後沒有重驗 source 上限 | `bounds-before.log` | 固定 runner 加 creation deny；apply 後同 bounds capture |
| Preparation cleanup 出錯仍可能宣稱 workspace removed | `cleanup-before.log` | 保留 typed cleanup error，禁止成功 report |
| bwrap 額外 new-session 使 runner 逃離原 owned group，早期 SIGINT cleanup 失敗 | `cli-cancel-before.log`、`session-escape-before.log` | 移除重複 setsid，保留既有 owner；拒 candidate setsid/setpgid；不延長 4.5s cleanup grace |
| checks 完成後 disk cleanup 吞 task/token 取消 | `cleanup-cancel-before.log` | shield/join 完成清理再傳取消，末端檢查 context；primary cleanup failure 不被另一 cancel 遮蔽 |
| Python default 第二 SIGINT 直接退出 cleanup | `double-sigint-failed.log` | 只在本 CLI command 暫存／恢復 handler；每次中止取消同一 task，沒有 global runtime owner |
| Private IPC namespace 可建 AS/scratch 之外的 semaphore/message queue | `ipc-before.json`／`ipc-before-full-output.log`、精確修前 runner `ipc-before/runner.py` | 真 namespace 中每類一個最小物件均成功，立即移除；加 semget/msgget/mq_open deny |
| Task 完成後捕捉的 SIGINT 仍可 exit0／print passed | `cli-late-signal-before.log` | 恢復 handler 後、輸出前重查本地 interrupted flag |

IPC 与 SIGINT 修正的依據包括 [Linux IPC namespace 文件](https://man7.org/linux/man-pages/man7/ipc_namespaces.7.html)、[Linux POSIX queue 實作](https://raw.githubusercontent.com/torvalds/linux/master/ipc/mqueue.c) 及 [Python 3.14 Runner SIGINT 行為](https://docs.python.org/3.14/library/asyncio-runner.html#handling-keyboard-interruption)。它們說明隔離／中止的機制；本機是否成立仍以實際 probes 和反例為準。固定 mounts／namespace options 與 syscall rules 對照 [bubblewrap options](https://github.com/containers/bubblewrap/blob/main/bwrap.xml)／[libseccomp API](https://github.com/seccomp/libseccomp/blob/main/doc/man/man3/seccomp_rule_add.3)，沒有猜新 SDK 或引入第三方 runtime。

## Compatibility, limits and remaining gates

- 支援的 profile 是 **標準庫 synchronous unittest 的單程序**，不是 SIRO 全套 pytest/dependency/GPU suite；`IsolatedAsyncioTestCase`、threads、subprocess、pip、其他 OS/interpreter profiles 不在認證範圍。未擴支援前 fail closed，不回 host 跑。
- **AS 是 virtual address space；tmpfs size 是 file data；它們不等於 aggregate RAM/cgroup limit。** Pipe buffers／inode metadata／trusted launcher overhead 不在整體記憶體 SLO 認證。一般多程序 aggregate resource gate 保留。
- **Source-only 是路徑 allowlist，不是語意 secret detector。** Owner 不應將秘密放入允許的可見 `.py`；本卡沒有掃私人內容。No-follow/stability checks 證明捕捉時 bytes，不是 hostile same-UID attestation。
- Local kernel、system interpreter／stdlib／libs、固定 runner 與 host source owner 為信任基礎；沒有 kernel exploit／供應鏈保證。候選可偽造自己的 unittest／stdout／exitcode，`passed` **永遠不是批准權**。
- 64KiB 限制計算保留的 **raw pipe bytes**；UTF-8 replacement 後 report／JSON bytes 可能不同。10s 是 process pipeline deadline；blocked arbitrary NFS/host IO 與 disk cleanup 總時限沒有認證，取消須 join owned IO 才回 caller。
- 尚無 model/Gateway automatic caller／autogeneration／enable／deployment；API owner admission／rate limit／product review 接線属于 RI-004 后續，不能把單次驗證當 background scheduler。
- CI 的 system Python／bubblewrap capabilities 未遠端驗證。本機 real-profile cases 全跑，其他平台若 skip 不得冒稱 OS verified。5 real-provider tests 未執行；本輪無 GPU、人耳、真人 Live2D、hardware／24h soak 或 deployment 驗收。

FIX-010 保持 VERIFIED；FIX-002 useful search、FIX-005 voice speed/human acceptance、FIX-006 understanding 保持 PARTIAL。已完成 RT-011／013／015 不重開、不重做。RI-004 可以設計符合此 profile 的一個 disabled read-only candidate／review 流程；**實際 enabled worker 不能繼承 patch-check 的驗收**。RI-005 launcher／single writer／latest-data-preserving rollback gate 不變。

## Rollback and rollout

立即停用方式：不要呼叫新增 `verify-patch`／async untrusted 入口；原 proposal/static review／可信 developer checks 保留。**禁止退回 host 執行不可信候選。**

Source rollback 只使用本卡 `repair.patch`：先 `git apply --reverse --check`，再在已停止呼叫此入口的 source checkout reverse；若 later edits 使 check 不符，人工比對 `before/`／`after/`，不要覆蓋整個工作區。實際 reverse/reapply 演練在 temporary tree 完成，沒有對共享 source 做試退。

不回復 DB、memory、ledger 或舊 backup；本卡沒有 schema/data migration。沒有重啟 8026、读取 private chats/DB/WAV/keys、改原聲線／cache、commit／PR 或正式發布。新 CLI 可由開發 checkout 明確執行，運行中的 SIRO 不因改 source 自動載入或獲得自改權限。
