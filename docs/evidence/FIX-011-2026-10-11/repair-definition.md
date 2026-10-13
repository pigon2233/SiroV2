# FIX-011 — Trusted skill worker 的有界輸入、輸出與程序清理

定義日期：2026-10-11（Asia/Taipei）。本文件定義最小修復與驗收，不代表修復已通過，也不批准安裝或啟用候選技能。進度與最終數據由本卡 REPORT／FIX_REGISTER 記錄。

## Source Task

既有 T19／A15 trusted-local skill worker；在 RI-004 實際 worker 接入前的 verification review 發現。D40／FIX-007 的完整 package identity 修復保留；D44 的待審候選準備切片不是此次缺陷的引入來源。

來源契約：[`D45 decision`](../../DECISIONS.md#d45--fix-011-trusted-worker-owned-lifecycle-repair2026-10-11)、[`D45 contract`](../../CONTRACTS.md#d45--fix-011-worker-process-ownership2026-10-11)。無法由目前證據確認哪個歷史 RT task 引入，故使用新的 FIX-011，不修改 RT 編號。

## Classification

**REQUIRED_FIX**。這是既有 API 的 lifecycle defect，應在後續 RI-004 worker 接入前局部修復。沒有證據證明已造成私人產品資料損害，不能列作已確認 production regression。

## Problem Source

**IMPLEMENTATION_BUG**，並有 **TEST_GAP**。不是已確認的 ORIGINAL_DESIGN_ERROR，也不是 registry 或 approval 修復卡；不建立 ARCHITECTURE_CORRECTION.md。

## Severity

**HIGH**。洪水可能使 manifest timeout 無法完成；取消窗口可能留下 owned worker／descendants。先修 parent ownership，再驗嚴格 worker profile，不靠擴大 timeout 或吞掉錯誤掩蓋。

## Problem

原 WorkerSupervisor 在 owned cancellation 區塊之前寫入並 drain stdin；stdout／stderr 只讀有限 bytes，卻先等待 process exit。超過保留量的輸出可能塞滿 pipe，清理也可能等待同一堵塞。取消時只 kill 直接 bwrap process，沒有整個 owned descendant lifecycle 的保證；bwrap 與 subprocess 重複建立 session，還有 child 自建 session 的退出窗口。

## Evidence

精確修前來源保存在本卡 [`baseline.json`](baseline.json) 與 [`before/`](before/)，基線 HEAD 為 `c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe`；先前完整回歸為 1,127 PASS，不代表新反例已覆蓋。

| 證據 | 修前 call path／結果 | 證據狀態 |
|---|---|---|
| [`before/src/siro/adapters/skill_worker.py`](before/src/siro/adapters/skill_worker.py) | `WorkerSupervisor.execute → _execute_one → create_subprocess_exec → stdin.write/drain` 位於 timeout/cancel try 之前；spawn／輸入取消尚未進清理區 | SOURCE_CONFIRMED |
| 同一修前檔案 | 有限 `stdout.read(output_bytes+1)`、`stderr.read(4097)`；`wait_for(process.wait())` 後才取 reader 結果；timeout/cancel 使用 `process.kill()` 再等待 process | SOURCE_CONFIRMED |
| 同一修前檔案 | `start_new_session=True` 並同時傳 bwrap `--new-session`，沒有 PID namespace | SOURCE_CONFIRMED |
| [`synthetic-probes.json`](synthetic-probes.json) 與 D45 | stdout／stderr 洪水在 manifest 1.5 秒到期後未返回，外層 5.004 秒才終止；spawn／stdin 取消返回時仍有 owned direct process／descendant；fork child 的 setsid 可離開原 PGID；100,000-character 合法 JSON／131,072-byte manifest output 上限仍回 invalid JSON | ACTUAL_SYNTHETIC_PROBES_CAPTURED；人工收尾後 running PIDs 為空。CPU soft-limit 可提高是 trusted-profile 限制，不是本卡 strict profile 成果；host canary read 是 PermissionError，沒有已證實 host read escape |
| [`worker-before.log`](worker-before.log) | 新 `tests/integration/test_skill_worker_lifecycle.py` 對精確修前來源的 RED 結果：**5 FAILED／9 deselected／0.51s**；合法大型 JSON／single＋repeated spawn cancel／over-limit＋nonfinite pre-spawn rejection 各反例失敗 | RED_CAPTURED；real bwrap cases 與 synthetic pre-spawn guard 分開，9 deselected 未執行，不能當 PASS |
| [`before/src/siro/services/tools/execution.py`](before/src/siro/services/tools/execution.py) | 已有 bounded argv 的 shared drain／sole PGID owner／shielded repeated-cancel cleanup；worker 尚未共用 | SOURCE_CONFIRMED；移到下層 adapter 並保留原入口，不再造 executor |

全部 runtime fixture 僅使用合成技能、temporary workspace／SQLite、synthetic marker；不讀私人 chat／DB／WAV／key，不操作 8026。

## Expected Behavior

合法 bounded JSON request 維持原 trusted-local skill input/output 契約。manifest 毫秒 timeout 控制 worker collect；stdout／stderr 無論是否超限都持續 drain，超量不能返回成功。任何 spawn、collect、timeout、取消或清理失敗均有同一 owner；取消確認前收完 owned process 與 request workspace，重複取消不截斷清理，也不產生晚到成功。

## Actual Behavior

修前輸入與 spawn 不完整受清理 owner 控制；有限 reader 與 process-first wait 存在 pipe 堵塞路徑，`read(n)` 也可能先返回尚未完整的合法 JSON；leader-only kill 和重複 session 不能證明 descendant cleanup。D45 觀測反例顯示這些窗口已可重現；原 A15 測試對一般 echo／CPU／memory／network 有覆蓋，沒有充分覆蓋這些 lifecycle 邊界。

## Root Cause

**已確認**：`_execute_one` 將 spawn／stdin drain 與 timeout/cancel ownership 分開；輸出讀取在保留上限即停止而未 drain；清理只處理直接 process；worker 沒有沿既有 bounded process owner，且產生兩個 session owner。

尚未確認任何 private-data damage、其他 OS 支援或整機 aggregate memory/cgroup SLO：**UNKNOWN — NEEDS INVESTIGATION**。不推論 registry、模型或 Runtime Evolution 整體設計有錯。

## Scope

只修既有 trusted-local worker parent lifecycle。將既有 process owner 放到較低層 adapter，services 入口保持相容；worker request 改為 owned read-only temporary 檔並有界讀取；使用同一 bounded helper drain、timeout、取消；bwrap 單一 session owner加 PID namespace。保留原 runtime/source mounts、manifest/schema／concurrency／registry／frozen snapshot identity。

本卡不新增 strict seccomp skill profile，不接產品 install／approval／enable／revoke／catalog，不升格 arbitrary generated skills，也不更改原權限。

## Files expected to change

既有三檔：

- `src/siro/adapters/skill_worker.py`：bounded request workspace、單一 process owner、取消與清理、輸出拒絕。
- `src/siro/services/tools/execution.py`：相容 facade，保留 API／errors／context 及既有 private signal monkeypatch 測試行為。
- `src/siro/skill_worker.py`：明確 request 檔讀取與 legacy stdin 有界讀取。

新增檔：

- `src/siro/adapters/process_execution.py`：原 bounded process implementation 的下層位置，無 services 反向依賴。
- `tests/integration/test_skill_worker_lifecycle.py`：本卡負向与回歸驗收。

任務記錄與 evidence 由主執行者另更新，不混入上述 source rollback 範圍。

## Files that MUST NOT change

- `src/siro/core/skills.py`、`src/siro/persistence/skills.py`、所有 migration／SQLite schema：完整 identity／舊 registry 語意保持。
- `src/siro/services/tools/skill_candidates.py`、`patch_verification.py`、`patch_verification_runner.py`：D43／D44 準備與驗證契約保持。
- Gateway、index UI、IntegratedCompanion、ToolCatalog／ToolOrchestrator、authorization／grants／policy：本卡不提供 execution authority 或產品新 caller。
- 模型／語音／body／browser／Rust／scheduler／release／launcher／lockfiles：不藉此修復擴大子系統範圍。
- 所有私人 runtime files、既有 DB／ledger／data，以及本卡基線以外的 dirty work：不得清理、還原或覆寫。

## Compatibility requirements

- `WorkerSupervisor.execute(skill, arguments)`、`SkillDispatcher`、complete package hash 與批准的 frozen identity 保持。
- 原 `services.tools.execution` 的 imports、ExecutionContext／ExecutionCancelled／ExecutionCleanupError、`execute_bounded_argv` 行為保持；timeout 支援 float 秒以保留 manifest 毫秒精度。
- 原 trusted-local Python／venv/source mounts 保持；不把現有 fork／exec 能力稱為 generated-code sandbox。
- request JSON 最大 65,536 UTF-8 bytes；拒絕 NaN／Infinity。這是明示的有界契約收斂；合法既有 object schema input 保持，超限不是靜默截斷。
- legacy direct worker stdin 保留但有界讀取；不新增 model-visible tool／自動 approval／權限。
- unsupported sandbox fail closed，無 host import 或其他未驗 profile fallback。

## Proposed repair

1. 先新增契約反例並對精確 before snapshot 留 RED。
2. 原 bounded process implementation 移到 adapter，services facade 保留原呼叫／private signal 相容性。worker 只向下引用，沒有第二套 process owner。
3. validate／serialize request（`allow_nan=False`）後，offloop 建立有界 owned temporary `request.json`，獨立 read-only mount `/request.json`；環境固定 `SIRO_SKILL_REQUEST=/request.json`。不得加入 package、污染 full digest 或引用 user path。
4. bwrap 去除重複 `--new-session`，由 shared helper 的 `start_new_session=True` 作 sole PGID owner；加入 `--unshare-pid`，保留 die-with-parent。清理不掃 host process 名稱或其他 session。
5. helper 使用原 shared stdout＋stderr drain budget，為 `max(manifest.output_bytes,4096)`；stdout 再驗 manifest 限制，任何 truncation、非 JSON／非 object／不合原 schema 都失敗。collect timeout 保留 `timeout_ms/1000`，cleanup 有独立 bounded grace。
6. request prep／spawn／collect／request removal 都 join owned 工作；重複取消不棄置，late cancel 不返回結果；typed cleanup failure 不變成一般成功或被吞掉。

## Tests required

- stdout 洪水、stderr 洪水與混合洪水：超量拒絕，持續 drain，manifest timeout／cleanup 不被 pipe 阻塞。
- 合法 request／exact byte bound；over-limit、NaN／Infinity、malformed JSON、nonobject、input/output schema refusal。
- cancel during request preparation、spawn、collect、request cleanup；single／repeated cancellation；spawn 後 cancellation 能回收剛建立的 process。
- owned descendant（包括子程序 setsid）於 timeout／cancel 後消失；不碰 fixture 外的 unrelated canary process。
- request cleanup failure 保留 ExecutionCleanupError；不偽稱 workspace 已移除。
- manifest 毫秒 timeout 不 round 成整秒；取消與完成同時到達時取消勝出。
- late cancellation 不返回成功；事件 loop heartbeat 保持；原 concurrency/key／frozen snapshot identity 不變。
- facade 的舊 import 與 `_signal_owned_group` monkeypatch 行為保持。

## Regression tests

既有 `test_skill_registry.py`、`test_skill_package_identity.py`、`test_bounded_execution.py`、`test_execution_lifecycle.py`；D43 `test_isolated_patch_verification.py`／`test_verify_patch_cli.py`；D44 service／Gateway／frontend candidate cases。最後完整 repository suite、type／lint／format／schema／diff checks；真 provider 未執行就明列未驗，不當 PASS。

## Acceptance criteria

- 新 lifecycle 反例在 exact before source 有可保存 RED，修後全部 PASS；原範圍回歸 PASS。
- 所有 owned worker／descendant 在 timeout 或取消確認後不存在，temporary request workspace 已清理，unrelated canary 保留。
- output flood／pipe stall 不能阻止 bounded collect 結束；失敗不得因延長測試或抑制 exception 轉 PASS。
- 所有 late／repeated cancellation 與 cleanup-error cases 誠實返回取消／失敗，無偽成功。
- 無 Core／adapter→services 逆向引用、無新增 executor、registry mutation、產品執行 caller／自動 enable 或 host fallback。
- 精確五 source/test 檔 reverse／reapply hash 驗證通過；其餘基線檔與既有 dirty work 保留。
- blocked host filesystem IO 的 cleanup SLO、aggregate kernel memory／cgroup、arbitrary generated-code execution 與 other-OS 支援未驗範圍保持明示，不以本卡解除 gate。

## Rollback method

先停用該 trusted worker dispatch 並 drain owned jobs；只逆轉本卡三個既有 source 檔的精確 diff，移除兩個新增 source/test 檔。使用本卡 before snapshots／repair.patch 與 hashes 在 temporary mirror 驗 reverse＋reapply，禁止 repository-wide reset／checkout。

不還原 DB／skills rows／ledger／私人檔，不移除 D40／D43／D44 修復或其他 dirty work。回退會重新暴露已確認 lifecycle 缺陷，因此 fallback 是維持 worker dispatch 停用，不能將舊 worker 當 safe generated profile。

## Risk

HIGH before repair，修後剩餘風險須依 actual evidence 判斷。process helper relocation 影響多個既有 caller，必須驗 import facade 與 private test hooks。PID namespace 在不支援環境可讓原 trusted-local worker拒絕，應 fail closed。輸入 64KiB 邊界與 strict JSON 可拒絕過去未受限資料，需明示兼容限制。request 與 source mount 仍屬 trusted-local：本卡不證明敵意同 UID、任意 code、memory aggregate 或長期 semaphore retention 安全。

## Roadmap handling

RI-004 的 strict worker 接入／真正安裝啟用路徑是 **BLOCKED_BY_FIX: FIX-011**，直到本卡驗收；D44 待審準備切片維持已驗成果，不重開。RI-005 的既有 release／latest-data／single-writer gate 獨立保留。其他不經 skill worker 的任務沒有證據顯示被本卡阻擋，原 RT 歷史不重編。

## Future activation findings — separate DEFER-gates

下列是未接入產品 activation 時必須滿足的 **REQUIRED_FIX／MISSING_INTEGRATION** gates；本卡先 DEFER 至對應 RI-004 接入切片，**不新增重複立即 FIX task，不修改 registry／approval／catalog**。這是可開始後續工作的條件，不把目前未啟用候選說成已壞掉的產品能力。

| 未來 gate | Evidence／已確認範圍 | 最小後續要求 |
|---|---|---|
| 同 id/version 的安裝不可覆寫別的批准 identity | `persistence/skills.py:35–38` 既有 trusted-local UPSERT 可換 hash／root／state；未接 product activation | 新產品 insert-if-absent／exact-identity path；同内容保留原 state，不同 hash／root 衝突拒絕，舊 trusted-local API 相容 |
| owner 啟用與撤銷綁正在看的 identity | `persistence/skills.py:49–81` 入參只有 id/version，CAS 綁 SELECT 到的 row，沒有 caller expected identity | 明確 expected hash＋root／完整 InstalledSkill CAS；client files／PASS 不能作 authority |
| 排隊時撤銷必須阻止開始 | 實際合成重現，見下段；Dispatcher enabled gate 在等待 WorkerSupervisor semaphore 之前 | product owner 先 unavailable，cancel/join 全部 admitted／queued tasks；或 semaphore admission 後的等價 exact gate；revoke 回應前清完 |
| 首次學習不能被 dormant descriptor 阻斷 | `skill_candidates.py:293–296` 對 hidden／unavailable exact aliases 都回 existing；ToolCatalog 當前只 constructor 登錄 | 第一次未安裝前不登錄 dormant 同名；安裝後／啟動讀到 exact installed package 才加到原 catalog；撤銷保留 unavailable，不造第二個 catalog |
| 保存可信待審證據與 owner 批准 binding | D44 report 只有 returned payload，沒有保留批准結果或 product install endpoint | 單份有 TTL 的 server-held review 綁 package/source/test/proposal digests＋owner；receipt 在 package 外，不接受 caller 送來程式與聲稱的測試結果 |
| mutation 取消不得留下晚完成写入 | `SQLiteStore.run_transaction` 直接 await `to_thread`；此為 source-only potential integration window，未宣稱本輪 product mutation 反例已執行 | activation owner 局部 shield/join mutation task，保留失敗狀態；不在 FIX-011 修改通用 store |

排隊撤銷的研究結果（2026-10-11，**SYNTHETIC ACTUAL DISPATCHER＋REGISTRY / MOCK WORKER**；原 terminal output 已觀測，獨立 log **NOT_PERSISTED**）：

1. Temporary SQLite 與 D44 固定 package，registry 安裝並啟用；建立原 SkillDispatcher／WorkerSupervisor。
2. 只替換 `_execute_one` 為記錄呼叫的合成 coroutine；第一個呼叫佔用原 concurrency=1 semaphore，第二個 dispatcher 呼叫通過兩次 registry gate 後排隊。
3. 確認第二個 waiter 存在；呼叫原 `set_enabled(..., enabled=False)`，`is_enabled(..., identity=skill)` 回 false；再放行第一個。
4. 實際 output：

```text
{'synthetic_only': True, 'production_worker_executed': False,
 'registry_disabled_before_second_start': True,
 'supervisor_calls': ['first', 'queued'],
 'queued_call_completed': {'text': 'queued'}}
```

已確認 root cause 是 gate 在 semaphore queue 之前；未執行真 worker／模型、無私人 DB、無 live service 操作。此結果不能當作新的 strict profile PASS，也不能當作目前已有 product revoke endpoint 失敗。
