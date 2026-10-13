# RI-004 D46 strict worker independent review

日期：2026-10-11（Asia/Taipei）。**Status: VERIFIED_SOURCE_REVIEW**。已凍結的七檔 D46 source／test及有界 synthetic probes 沒有剩餘已確認 scoped blocker；owned strict tests／完整回歸／精確 rollback均已有實際證據。本review不代替任意生成程式的安全認證或產品批准。

本輪沒有修改 production、tests、roadmap 或全域文件；只寫 owned evidence。所有 probe 使用 temporary synthetic package／host marker；沒有讀私人對話、DB、金鑰或 WAV，沒有模型呼叫、live 8026、registry activation 或產品部署。

## Scope and source binding

本卡只有六個 production files 及一個新 test：既有 `adapters/skill_worker.py`、`services/tools/patch_verification.py`、`services/tools/patch_verification_runner.py`，新增 `adapters/isolated_python.py`、`adapters/python_restrictions.py`、`adapters/strict_skill_runner.py`、`tests/integration/test_strict_skill_worker.py`。

[`independent-source-binding.json`](independent-source-binding.json) 已於 source／test freeze後重新產生；exact SHA-256全部與主執行者 [`preservation.json`](preservation.json) 的final七檔相同。讀取 before module後真正呼叫原 `_mounts`／`_sandbox_argv`，與新 facades 的 mounts／argv 完全一致；不是僅比函式名稱。

已確認 default trusted-local `execute`／`execute_one` 原 body、request helpers、完整 Dispatcher AST 不变。Patch runner main／原 probe marker與test discovery AST 不變；`restrict()` 可被既有 tests import／monkeypatch。九個保護來源（Core skill、registry／SQLite、D45 process owner／legacy CLI／service facade、D44 preparer、catalog／orchestrator、Gateway）與本卡 baseline hash 相同。新 adapters 沒有 reverse service import；沒有第二個 process owner、registry、planner、DB 或 sandbox denylist。



| Frozen file | SHA-256 |
| --- | --- |
| `src/siro/adapters/skill_worker.py` | `5f9e10546d7f894666d7ca9773c6ef56ee27b7fbd5c0787e4b1b792e08221f22` |
| `src/siro/services/tools/patch_verification.py` | `f2ce3ce3e271c5ce5a725ef32e1c489f2f437acd6199594c7fe3e6fe1c7e59b3` |
| `src/siro/services/tools/patch_verification_runner.py` | `c88836472600bbcc9b08d6497a3d759d531a07653e3c194888737f0bb7d72e96` |
| `src/siro/adapters/isolated_python.py` | `db76ee0f908bbea241a51b7566ea74af0917b34eb378c4179710ed1b5cd327e0` |
| `src/siro/adapters/python_restrictions.py` | `66a4d2185ea25a50fa7f4f20f304700de229e91f37036c20df8a43d3d0134908` |
| `src/siro/adapters/strict_skill_runner.py` | `f66724482c3681759f989684fe7c31fbfc3e5b2c6fcadfd1e4e7b1d76098ef2b` |
| `tests/integration/test_strict_skill_worker.py` | `f4ab32e49e02b76a3f8961a0bf9995f814ea44fd5933748916d8d4809465b04f` |

## Confirmed findings and local repair

| Finding | Evidence and confirmed root cause | Repair / verification |
| --- | --- | --- |
| 完整身份比對漏掉 JSON boolean／number 的語意差異 | [`independent-schema-identity-probe.json`](independent-schema-identity-probe.json)：實際 strict OS worker 的 supplied schema把 `additionalProperties: false` 改為 `0`，Python equality與hash仍相同；genuine拒extra input、forged實際執行。 | Strict private canonical metadata check 使用 `model_dump(mode="python")`＋`json.dumps`；不能用 Pydantic JSON mode，該 mode會把 forged manifest `True` 轉成 `1`。後續 validation／deadline／limits／output schema 都用 verified captured identity。[`independent-identity-admission-after.json`](independent-identity-admission-after.json) input／output False/0及manifest True/1均拒絕，genuine正常。 |
| strict admission 使用未驗 concurrency，可能永遠等不到 semaphore | [`independent-admission-probe.json`](independent-admission-probe.json)：actual supervisor supplied manifest concurrency=0，0.2s outer timeout才取消。Static guard位於 wait之後。 | Strict guard提前至 semaphore配置／wait前；同 [`independent-identity-admission-after.json`](independent-identity-admission-after.json) 已驗 immediate unsupported。Default caller body不變。 |
| 相對 collect timeout 可接受絕對 deadline之後的成功結果 | [`independent-deadline-probe.json`](independent-deadline-probe.json)：real strict OS worker＋controlled execution spawn-publication delay0.35s；manifest200ms在0.3899s回成功。Budget在spawn前計算，collect在spawn後開始，缺absolute fence。 | Strict caller傳既有 `ExecutionContext(deadline=...)` 給原 process owner；probe與execution共用同一context/deadline。[`independent-deadline-after.json`](independent-deadline-after.json) 相同controlledcase變timedout，兩process已reaped。0.6405s含owned cleanup grace，不是200ms wall-clock cleanup SLO。 |

上述都是未完成 D46 卡內的局部實作修復；沒有新增重設需求，也不把 prior trusted-local metadata equality debt當成本卡已修產品批准路徑。

## Actual OS and ownership assessment

[`independent-os-probes.json`](independent-os-probes.json) 與可重播 [`independent_os_probes.py`](independent_os_probes.py) 有 actual strict bwrap／seccomp：合成 host marker不可見、讀寫都拒絕，`/proc/1/root`不提供host root；marker原值保留。Candidate／trusted files readonly，scratch合法8KiB可写。Socket／fork／exec／setsid／setpgid及memfd／shmget／keyctl／io_uring creation拒絕；no_new_privs=1、seccomp=2，raw readonly getrlimit證明AS64MiB與CPU1s的soft/hard相同。100MiB配置MemoryError，超過1MiB檔案EFBIG。Environment只有LANG／TMPDIR與bwrap PWD，不繼承host caller environment。Temporary package／marker全部移除。

這些證明有限 boundary與正負控制，不認證任意生成程式安全、aggregate kernel memory、任意 stdlib call、其他 OS或host runtime供應鏈。Python `resource.getrlimit` 會走已拒絕的prlimit64，完成probe改用raw readonly getrlimit；這是probe修正，沒有要求放鬆限制。

Strict runtime只有固定system CPython3.14／stdlib／必要shared libraries，沒有venv、production source、whole `/usr`／home／host device或secret mounts。`-I/-S/-B` 的runner顯式暫加 `/trusted` 載已固定的readonlyrestrictions，再移除該searchpath；candidate importpath只在不可逆限制後加入，沒有讓candidate同名module搶載trustedhelper。Probe只讀limits、裝限制並回精確marker，不importcandidate或request。Candidate自行輸出PASS／exit78不能取得批准。

Capture／write／remove都offloop，snapshot bytes來自同次capture；post-freeze原檔改動不替換本次execution。Strict input request仍共用D45 64KiB finite JSON／readonly ownedworkspace；trusted limits在packageidentity之外但值只取verifiedmanifest。Default metadata／registry／Dispatcher不放寬。Legacy `_prepare_skill` 一般Python equality是既有trusted API限制，未被新caller提升為產品批准來源。

Shared process owner只有一個PGID/session；bwrap PIDnamespace／deny fork/exec限制維持。Preparation、spawn、read/drain、workspace cleanup已有join；normal late cancellation不報成功，primary ExecutionCleanupError在finally cleanup被保留。新增strict caller沒有自己的kill/reader/semaphore owner替代原helper。下節log包含controlled actual probe spawn cancellation及execution cancellation、offloop capture／cleanup cancellation與typedcleanup拒絕；source推論與actualcase分開。

## Verification and release status

已讀實際log：[`strict-tests-final.log`](strict-tests-final.log) **51 PASS／4.71s**；[`adjacent-final.log`](adjacent-final.log) **120 PASS／16.90s**；[`full-suite-final.log`](full-suite-final.log) **1,202 PASS／5 deselected／3 warnings／132.67s**。既有real-provider tests未執行，沒有live／模型／人工產品驗收。

[`lint-final.log`](lint-final.log) PASS；[`format-final.log`](format-final.log) 295files格式一致；[`types-final.log`](types-final.log) 230sourcefiles无typeerrors；schemas成功命令的 [`schemas-final.log`](schemas-final.log) 沒有診斷。Secret／diff等主驗收細節以REPORT為準，沒有另作未執行聲稱。

[`rollback.json`](rollback.json) 是disposable exact七檔 reverse/check/reapply：before三檔restored、新四檔removed、candidate七檔reapplied、live source未變、没有DB rollback或runtime restart；[`preservation.json`](preservation.json) 顯示254baseline中251existingfiles保持，只有expected三既有檔修改。本review再核對其final hashes與independentbinding一致。

API constructor before兩FAIL是缺少strictprofile入口；`strict-identity-before.log` 三FAIL、`strict-admission-before.log` 一FAIL、`strict-deadline-before.log` 一FAIL分別是本文三個局部反例，不把beforecollection當作OS RED。最終51PASS覆盖同反例及真OS／controlledlifecycles；mockprobe拒絕不能代替actualworker boundary證据。

## Remaining product gates

本卡提供 **developer explicit verification API**，不是可自行啟用的產品能力。D44 report仍installed=false／enabled=false／authorizes_execution=false；沒有Gateway／model tool／install／enable／revoke入口。

下一切片保留 [`FIX-011 activation gates`](../FIX-011-2026-10-11/repair-definition.md#future-activation-findings--separate-defer-gates)：bounded server-held review、owner-bound完整package身份批准、install-disabled／明確enable、同id/version不可換碼覆寫、使用原ToolCatalog及Dispatcher、先不可用再cancel/join queued＋active jobs的revoke、IO cancellation join與close。已確認的queued revoke gap不能用registry disable alone帶過；不在D46混入第二個owner或修改registry。

外部dependencies／threads／multiprocess／其他OS、delegated cgroup aggregate kernel RAM SLO、blockedhostIO cleanup SLO、同UID敵意／runtime supply chain、安全審查、長期retention、人工作品驗收與RI-005 release仍未驗。RI-004整體保持PARTIAL；任何狹窄worker PASS不會自動解除這些gate。

如果所綁定的七檔有變更，應對差異重新查核，不將本review沿用到不同source。

## Root final verification addendum — 2026-10-11

上方PENDING是獨立probe完成時的原紀錄，保留來源；主執行者其後確認七檔source/test已凍結，重跑原independent_source_binding.py，hash與preservation final完全一致。51PASS／完整1,202PASS／5real_provider未選／3既有warnings、Ruff295／mypy230／schema/diff與exact7rollback PASS；secret source0／evidence316逐項SHA誤報核對。此段是root驗收補記，不冒稱獨立agent執行了完整suite。最終交付與限制見REPORT.md。
