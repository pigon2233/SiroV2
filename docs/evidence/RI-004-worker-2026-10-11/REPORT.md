# RI-004 — 固定 stdlib 技能的實際隔離執行

日期：2026-10-11；HEAD `c1d2d41` 的既有 dirty workspace。**D46 Linux x86_64／system CPython3.14／固定 stdlib single-process worker 切片 VERIFIED；RI-004 整體 PARTIAL。** 沒有正式部署或啟用對話技能。

## A. Current State

固定 Markdown checklist 候選已能真正執行：原 D44 `SkillCandidatePreparer` 準備／RI-003 驗證後，developer verification fixture 將同一四檔完整身分交給 `WorkerSupervisor(profile="python-stdlib-single")`，正確輸出中文待辦／完成項及數量、忽略 fenced code。不是 host import 或 mock worker；沒有 registry install／enable。[實際結果](actual-worker.json)。

## B. Codebase Memory Status

本輪未暴露 Codebase Memory MCP，未 query／重索引、未繞 owner lease，沒有聲稱圖譜更新。直接 source／AST／callers、254 個 public source hashes 與實際 probes 作核查；開發知識不作 runtime 記憶或授權。

## C. Architecture Findings

共用先前 RI-003 mounts／bubblewrap argv 與不可逆 OS restrictions，下移到 adapters；patch verifier 保留原 private facade 和 runner probe／main 語意。只新增明確 strict profile，不做第二個 process owner、registry、sandbox denylist、scheduler 或 schema engine；default trusted-local D45 body／Dispatcher 保留。[獨立 source binding](independent-source-binding.json)。

獨立 review 抓到並以 RED→最小局部修復驗證三個尚未啟用 slice 的實作缺陷：Python equality 的 False／0、True／1 身分混淆；未驗 concurrency=0 先進 semaphore 掛住；相對 timeout 漏過 delayed spawn。Strict canonical metadata 使用 Python-mode manifest dump 保留實際型別，再 JSON 比較；parent 驗輸入／輸出與限制都使用 verified captured identity。Static admission 移到 queue 之前，probe／execution共用既有 absolute ExecutionContext。沒有改 Core／舊 schema subset 或一般 process helper。

## D. Implemented Changes

- Explicit strict profile 只接受四檔固定入口、空 permissions／observe／read_only／network denied／single concurrency／process cancellation，有限 CPU／AS／timeout／output；未知或超範圍明確拒絕，沒有 trusted fallback。
- Complete package capture、身分核對、readonly frozen candidate 與 trusted runner/request/limits 的準備／移除都 offloop；真正執行同批 bytes，原 package 不寫入、不污染 digest。
- Trusted runner 用 system Python `-I/-S/-B`，先限制，再加入 candidate import path。最小 runtime／readonly candidate/trusted／新 proc/dev／8MiB scratch，沒有 venv、production source、whole `/usr`、home／私人資料 mounts。
- 同一 irreversibile seccomp deny 與 hard RLIMIT；不能 fork／exec／socket／改 session／提升 limits／建立被拒 kernel objects。Probe 不 import candidate、只接受固定 marker；失敗 fail closed。沿 D45 bounded drain／PGID ownership／repeated cancellation／typed cleanup failure。

## E. Tests and Verification

| 驗收 | 實際結果 | 證據 |
|---|---|---|
| 修前 profile interface | **2 FAIL／0.11s**；exact pre-card projection亦確認缺 constructor profile。41個當時新 tests僅collect，沒有OS執行，不能稱41個FAIL | profile-before.log；complete-before.json |
| 独立反例 | identity3FAIL、admission1FAIL、deadline1FAIL；初次修後 JSON-mode manifest仍1FAIL／5PASS，改Python-mode後6PASS | strict-identity-before/after/final.log、strict-admission-before.log、strict-deadline-before/after.log |
| 新 strict cases | **51 PASS／4.71s**；独立再驗51PASS／4.73s | strict-tests-final.log、strict-audit-final.log |
| 相鄰回歸 | **120 PASS／16.90s**；原RI-003專項38PASS／8.98s | adjacent-final.log、patch-profile-after.log |
| 完整離線 | **1,202 PASS／5 real_provider未選／3既有warnings／132.67s**；保留原1,151加51，不與focused重複相加 | full-suite-final.log |
| 真 fixed parser 鏈路 | ServicePreparer→real patch verification→complete package hash→actual strict worker→expected output／cleanup PASS | verify_worker.py、actual-worker-final.log、actual-worker.json |
| 獨立 OS probes | host marker/env不可見／writes拒絕、socket/fork/exec/session/limits/IPC拒絕、AS／CPU／file限制正負控制 PASS | independent-os-probes.json、independent_os_probes.py |
| 靜態 | 全repo Ruff lint／format295、mypy230、schema／diff PASS | lint-final.log、format-final.log、types-final.log、schemas-final.log |
| 保存／回退 | baseline254中251不變；3既有修改／4新增，exact7 temporary reverse/check/reapply bytes完全一致 | preservation.json、rollback.json、verification-final.log、verify_source.py |
| Secrets | source7檔0；owned evidence316項逐一與detector SHA1核對為記錄的package/source/artifact digest，unresolved0，all-files／no network verification | secrets-source.json、secrets-evidence-final.json、secrets-review-final.json |

Actual OS測試覆蓋 import-time 與 run-time 限制、CPU／AS／file／scratch／output floods、malformed UTF-8、unsupported sandbox 不 import；actual probe與execution spawn取消／PID消失。受控 timing fixtures驗 offloop prep/cleanup joins、primary error、late取消和絕對期限，不把受控 delay當日常 latency benchmark。200ms deadline delayedspawn修後0.6405s含獨立cleanup grace，不能稱200ms end-to-end SLO。[獨立 review](independent-review.md)。

## F. Risk Assessment

認證範圍限此 OS/runtime／single-process／stdlib profile。AS／file-data／scratch不等於 cgroup aggregate kernel RAM；同UID敵意、runtime supply chain、blocked host IO cleanup SLO／semaphore retention未認證。Candidate可以撒謊或偽造 output，probe/PASS不作批准。Generic JSON schema只沿既有subset，沒有宣稱 nested array/items/count invariant全部已驗；固定產品 caller仍須本地輸出契約。

## G. Recommended Next Tasks

沿 RI-004 接成產品流程：bounded server-held review／package-bound owner審閱、install-disabled／explicit enable、same-version collision refusal／exact identity CAS、先停止admission再cancel/join queued與active的revoke，接原ToolCatalog→ToolOrchestrator→SkillDispatcher。UI依可觀測真狀態顯示操作，模型不能批准自己的新技能。保留既有完整 package 身分、D45、D44 與政策邊界。

## H. Deferred Work

任意生成程式、外部依賴／threads／multiprocess／其他 OS、aggregate cgroup驗收、runtime MCP、自動部署與 RI-005 latest-data rollback未交付。FIX-002搜尋、FIX-005速度／人工聽驗、FIX-006理解品質仍各自PARTIAL；原RT-011／013／015 DONE切片不重做。

## Scope and rollback

本卡精確七檔：既有 worker adapter、patch verifier與runner；新增 isolated_python、python_restrictions、strict_skill_runner及strict tests。Core／registry／SQLite／process owner／D44 service／Gateway/UI／模型／語音／body／permissions／locks不變。沒有讀私人chat／DB／WAV／key、呼叫模型/GPU、重啟live8026、registry activation或正式部署。

回退 SHA256 `d6e0bcbae70eafc6c0c469934682e469947d8220af14f33932cdeb8a09679725`。先停止strict dispatch、drain，逆本卡精確source patch；演練只在temporary mirror，不操作live source／DB或撤前序dirty工作，保留FIX-011修復。不能退回trusted profile跑不可信候選。
