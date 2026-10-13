# RI-004 — D46 strict worker 切片定義與驗收

日期：2026-10-11（Asia/Taipei）。**Status: VERIFIED_DEVELOPER_PROFILE**。本文件定義開發者可明確選用的固定 stdlib single-process worker；本卡 source／有限OS／regression／exact rollback已驗收，產品安裝、批准或啟用仍是另一切片。

## Source Task / classification

RI-004 剩餘 worker gate；依賴 FIX-011 D45 lifecycle 修復已通過，來源決策為 [`D46`](../../DECISIONS.md#d46--ri-004-固定-stdlib-single-process-worker2026-10-11) 與 [`D46 contract`](../../CONTRACTS.md#d46--ri-004-strict-worker-contract2026-10-11)。分類為 **REQUIRED_FIX／MISSING_INTEGRATION＋TEST_GAP**：原 trusted worker 的 profile 不足以接入未受信任候選，並非已證實 D44 regression 或原整套 Runtime Evolution 設計錯誤；本切片沿既有 WorkerSupervisor 加 explicit profile，不另造 registry／executor。

Severity: **HIGH（接入 gate）**。沒有 private-data damage 或 product activation 問題的實際證據。

## Problem / expected and actual behavior

原 default trusted-local worker 已有 FIX-011 input/output／process ownership 修復，仍使用 venv、production source 與較廣的 OS mounts，允許 fork／exec，RLIMIT_CPU soft limit 可提高至 hard limit。這是已明示的 trusted-local 限制；不能當作新候選的 strict boundary。

預期提供唯一 explicit `WorkerSupervisor(profile="python-stdlib-single")`：只驗有限 OS／runtime／manifest／package；完整身份一致的 captured bytes 才交給固定 trusted runner。候選 import 前裝不可逆限制；不支援／probe 失敗不得 host import 或退回 trusted worker。預設 `trusted-local` 保持 D45 相容，未知 profile 拒絕。

目前此接口在本卡 before snapshot 缺少；正式 proof 尚待新反例與 actual OS 驗收，不將 API existence 當成安全證明。

## Evidence / root cause

- 本卡 [`baseline.json`](baseline.json) 與 [`before/`](before/) 保留精確 dirty source；D45 前輪完整結果 1,151 PASS／exact five-file rollback，不能代替本卡測試。
- [`strict-api-before.json`](strict-api-before.json) 是 explicit strict API 的修前負向記錄；僅在該檔實際存在與內容確認後引用其結果，不預填 PASS。
- D43 已驗證 Linux x86_64／system CPython 3.14 的最小 runtime mounts、bwrap、不可逆 seccomp／hard limits與唯一 process owner；本卡必須重用到下層 adapter，原 patch caller 留 thin compatibility delegates。
- D45 synthetic probes 的 CPU soft-limit raise／可 setsid descendant，證明 default trusted profile 無法自動升格。FIX-011 已修 descendant lifecycle，不表示所有 syscall／mount／aggregate memory gate 已完成。

已確認 root cause：缺少 explicit strict WorkerSupervisor profile 與專用 trusted worker caller；已驗 restriction 機制目前位於 patch-specific service runner。這是局部介面接入與層級歸屬，不須重設 SIRO Core。其餘 OS／kernel aggregate／同 UID 敵意行為沒有完整證據：**UNKNOWN — NEEDS INVESTIGATION**。

## Minimal scope / expected files

- 既有 `src/siro/adapters/skill_worker.py`：explicit profile、strict manifest/full identity capture、owned workspace／probe／worker execution／cleanup。
- 既有 `src/siro/services/tools/patch_verification.py`：原 `_mounts`／`_sandbox_argv` 保留相同 signatures，delegating 下層共用 implementation；準備時放入同一 trusted restrictions module。
- 既有 `src/siro/services/tools/patch_verification_runner.py`：保留 `restrict`／main／private test seams，使用固定 trusted module，原 probe marker／patch test behavior 不變。
- 新 `src/siro/adapters/isolated_python.py`：D43 runtime mounts／sandbox argv 的下層共用位置。
- 新 `src/siro/adapters/python_restrictions.py`：同不可逆 no_new_privs、hard limits與 seccomp；parameters 只能收緊預設 memory／CPU caps。
- 新 `src/siro/adapters/strict_skill_runner.py`：sandbox entry 固定 `/trusted/runner.py`；不能由 caller／candidate 指定 runner 或 entrypoint。
- 新 `tests/integration/test_strict_skill_worker.py`：strict worker 契約／actual OS tests；沒有既有 assertion 刪除／放寬來讓新profile通過。

若檔名與此定義的尚待確定項目不同，以 source manifest 明示更新，不能隱藏多出的修改範圍。

## Files that MUST NOT change

Core skills／authorization／grants／policy、SQLiteSkillRegistry／SQLiteStore／migration／DB schema、ToolCatalog／ToolOrchestrator、Gateway／UI／IntegratedCompanion、D44 candidate preparer、D45 process owner／legacy worker CLI、模型／語音／body／Rust／scheduler／release／launcher／lockfiles，以及任何 private runtime files。

本卡没有 server-held review、install／enable／revoke、model tool、automatic approval 或 deployment；不以 strict profile 接口自行取得執行權限。原 registry／Dispatcher 的批准與 frozen snapshot 完整 identity gates保留。

## Compatibility / strict admission requirements

- Default `WorkerSupervisor()` 等同 `profile="trusted-local"`；`execute(skill, arguments)` 原 signature 保持。Unknown constructor profile ValueError；不會被默認成 trusted。
- 只 Linux x86_64／固定 system CPython 3.14。缺 runtime、namespace、filter 為固定 `SkillExecutionError("strict skill sandbox unavailable")`；unsupported manifest/package、identity mismatch 各用 D46 固定分類。無 fallback。
- 精確四個 captured normal files：`manifest.json`、`input.json`、`output.json`、`plugin.py`；固定 `python:plugin:run`，permissions 空、risk observe、read_only、network denied、concurrency 1、process cancellation、compensation none。
- 原模型下限保持；memory≤256MiB、CPU≤5s、output≤131072bytes、timeout≤10000ms。Request JSON≤65536 UTF-8 bytes／no NaN或Infinity；raw output 保留上限／strict UTF-8／object schema subset 同 D45，不宣稱完整 JSON Schema。
- Static capture 不 import candidate；supplied full identity 必須與 captured current package 相同；所有 frozen candidate bytes 來自同次 capture，不能從 user root 再重讀代換。
- readonly request／limits／provenance 在 package identity 外；候選碼不能修改這些配置或借另一 root 的批准。

## Proposed implementation invariants

1. 新 profile 僅在既有 supervisor 明確選用；先跑 constructor／manifest／identity／unsupported 反例，再實作。
2. D43 sandbox argv／restrictions 移到下層共用位置，原 patch caller delegates；不複製第二份 denylist，也不在 adapter import services。
3. trusted runner 在 `/trusted`，先載 trusted stdlib 與固定 readonly config。`-I` 不依 script directory search path：restrictions 載入必須顯式使用固定 trusted 來源，之後撤掉臨時 `/trusted` search path，candidate path 只在 irreversible restrictions 後加入。
4. Probe 只讀同一 limits／runtime，裝同一限制後回精確 `SIRO_SKILL_PROFILE_READY_V1\n`；不 import plugin／候選 request，不接受 candidate PASS。Marker 不精確、非零、truncated 都 fail closed。
5. Probe 与 actual execution 共用同一 manifest collect deadline，actual entry 固定 plugin.run。只使用 FIX-011 sole process owner；strict failures 不降級到 trusted-local。
6. stdout＋stderr shared drain，strict UTF-8、raw output bound、JSON object與原 schema validation；probe result／candidate output永遠不是批准權。
7. capture／workspace IO offloop；prep／spawn／run／cleanup single＋repeated cancellation join，late cancel 不成功，primary ExecutionCleanupError 不被 request／snapshot cleanup mask。

## Tests required

**API/static/compatibility**：explicit/default/unknown profile；unsupported manifest 的每個維度；extra/dependency/native file、schema/path／symlink／hardlink alias；supplied manifest/schema/root/hash 換碼與 forged identity 不達 candidate；舊 trusted worker與 D43 private imports／markers／test seams 維持。

**Trusted startup/probe**：system -I/-S runner 能載固定 restrictions；probe 前後 candidate canary 不被 import；同 limits／runtime／deadline；bad marker／非零／truncated／unsupported 不啟動 actual candidate；沒有 fallback call。

**Actual OS**：D44 固定 checklist parser輸入／輸出；合成 host read/write canary／env 不可見；socket／fork／exec／setsid／setpgid／limit raise／IPC／keyring creation denial；CPU／AS／scratch／FSIZE／stdout／stderr flood；合法完整 bounded JSON／U+FFFD、非法 UTF-8／JSON／nonobject refusal。不得讀真 host secrets 或以危險壓力分配取代小型 syscall probe。

**Lifecycle**：prepare／probe／actual spawn／run／cleanup single＋repeated cancel，所有 owned PID 消失／unrelated canary 保留；event-loop heartbeat；cleanup refusal typed，late cancel 不返回成功；post-freeze來源改動不能替換本次 worker bytes。

**Regression**：FIX-011 worker lifecycle／D40 identity、D43 patch／CLI、D44 service／Gateway／frontend、bounded process owner；最後完整 repository與 static／type／schema／diff／secret checks，沒跑的真 provider／人工驗收分列。

## Acceptance criteria

- 新 caller／unsupported／static／OS 反例先留可重播 RED；修後 scoped cases PASS。Runtime unsupported 的 cases 是 fail-closed proof，不可算 arbitrary OS 支援成功。
- 真 strict worker能執行固定 D44 parser，negative probes 全部按預期拒絕，候選沒有 host import、private mount／secret env／network／fork／exec／session／limit升級入口。
- Probe 与 execution deadline、runtime、limits binding 明確；失敗不觸發 fallback，不把假 marker或 fake tests 當 authority。
- task cancelled或cleanup失敗不產生成功，owned workspace/PID誠實清完；若清理未確認即保留失敗 gate。
- D43／D45 unchanged contracts 与完整 regression通過；精確 source reverse／reapply hash 通過，baseline非scope dirty work保留。
- 獨立 source/caller audit沒有剩餘已確認 scoped blocker。產品尚無 install/enable／approval caller，RI-004整體仍 PARTIAL。

## Rollback method

停止這個 explicit strict profile 的新 dispatch 並 drain owned jobs；只 inverse 本卡精確 source patch／移除新增 source與tests，保留本卡 before snapshots和hashes。不得 repository-wide reset，不回退 DB／registry rows／ledger或私人檔；不得用 trusted-local fallback替代失效 strict profile。D45 FIX-011已驗 lifecycle 修復保留。

## Risk / remaining gates

這個 profile只有 stdlib synchronous single-process，threads／pytest／外部 dependencies／其他 OS／多程序都不是支援範圍。RLIMIT_AS 與 scratch 不是 cgroup aggregate kernel RAM SLO；trusted OS／runtime／同 UID assumption、blocked host IO cleanup SLO及長期 retention未認證。候選可撒謊／自行退出／偽造 output，父程序只能驗 boundary／contract，不能由結果自行批准。

Server-held review、security review、owner-bound approval、install-disabled、explicit enable、revoke／catalog／對話產品入口是下一個獨立切片。該切片需要滿足既有 [`FIX-011 future activation gates`](../FIX-011-2026-10-11/repair-definition.md#future-activation-findings--separate-defer-gates)，不在本卡混入 registry／UI。RI-005 release gate不變；RT歷史不重編、不重做已解決的問題。

## Verification record

Exact六production＋一test綁定、actual／mock區分及source審查見 [`independent-review.md`](independent-review.md)；owned strict suite51PASS／4.71s、adjacent120PASS／16.90s、完整repository1,202PASS／5deselected／132.67s；static／type與disposable exact七檔rollback已有實際log／JSON。詳盡final紀錄由本卡REPORT持有，不將本狹窄驗收提升為產品批准或任意sandbox認證。

獨立實作反例已捕捉三項本卡局部缺陷，屬 **REQUIRED_FIX／IMPLEMENTATION_BUG＋BAD_INTERFACE**，不是原系統重設理由：

| Defect | Confirmed source / evidence | Minimal correction / current verification |
| --- | --- | --- |
| supplied schema `False → 0` 被 Python equality 當作相同，額外 input field 實際進入 worker | `_prepare_strict` 原 `current != skill`；[`independent-schema-identity-probe.json`](independent-schema-identity-probe.json)，真正 strict OS worker，genuine 拒絕、forged 成功。 | Strict 專用 type-sensitive JSON metadata equality；verified captured schemas／manifest 才是後續 validation／limits 的來源。Pydantic `model_dump(mode="json")` 會把 forged manifest `True` 轉成 `1`，故 canonical metadata 使用 `mode="python"`。[`independent-identity-admission-after.json`](independent-identity-admission-after.json) 已驗 input／output False/0、manifest True/1 全拒絕，genuine 可用；最後 source binding 仍待本卡 freeze。 |
| forged zero concurrency 在 admission 前形成不能進入的 semaphore | `WorkerSupervisor.execute` 原先使用 supplied concurrency 後才跑 strict guard；[`independent-admission-probe.json`](independent-admission-probe.json) 在 controlled 0.2s outer deadline 才被取消，未啟動 OS worker。 | Strict guard 在 semaphore allocation／wait 前；同 [`independent-identity-admission-after.json`](independent-identity-admission-after.json) 已驗立即 unsupported，default trusted-local 不改。 |
| shared deadline 的 remaining budget 在 spawn 前計算，但 helper 從 spawn 後使用 relative timeout，晚結果可能成功 | [`independent-deadline-probe.json`](independent-deadline-probe.json)：真 worker配合 controlled 0.35s spawn-publication delay，200ms manifest 在 0.3899s 回成功、兩 process 已 reaped。這不是普通產品延遲測量。 | 在 strict caller 沿既有 process helper 接入 absolute deadline，不另造 process owner。[`independent-deadline-after.json`](independent-deadline-after.json) 已驗同controlledcase變timedout、兩realprocessreaped；elapsed含boundedcleanupgrace，不聲稱200mswall-clockcleanupSLO。 |

[`independent-os-probes.json`](independent-os-probes.json) 是單次真正 OS boundary 正負控制：合成 host marker（含 `/proc/1/root` 路徑）不可見／不變，candidate／trusted readonly，socket／fork／exec／session／memfd／shm／keyring／io_uring 拒絕，64MiB AS／1s CPU 的 soft與hard一致，超過 1MiB file與100MiB allocation被拒絕，合法8KiB scratch可用，no_new_privs=1／seccomp=2。Environment只有 LANG／TMPDIR 與 bwrap 自加 PWD；沒有繼承 host caller env。最初 probe直接用 Python `getrlimit` 會因同一 `prlimit64` restriction 被拒絕，完成版用 readonly raw `getrlimit` query；不把此 probe 編寫修正算成產品缺陷。

上述獨立反例沒有新增立即 FIX 編號：它們在尚未完成的 D46 卡內先 RED、局部修正、再驗收。產品 install／enable／revoke 和 aggregate kernel RAM 等 gate 仍保持。
