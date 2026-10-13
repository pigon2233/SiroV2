# FIX-007 — 批准的技能與实际執行 package 一致

DONE / VERIFIED，2026-10-10，限定 D40 本機 Python package／既有技能元件。Source：T22、2026-10-09 review；REQUIRED_FIX / HIGH；IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP。沒有實際 production事故／RT regression證據。

## 修復

原 manifest_hash只含三個JSON，plugin/helper/dependency/data換碼仍同hash；Dispatcher只查id/version。使用expected rejection tests，原碼确實讓changed package到recording supervisor。最終43新cases套精確原三個source：42 FAIL／1 PASS；source import路徑與SHA已核對，不是誤跑新碼。[完整修前](complete-tests-before.log)、[來源證明](complete-tests-before.json)。

只改 core/skills.py、persistence/skills.py、adapters/skill_worker.py，原五欄InstalledSkill與SkillManifest v1保持。沿manifest_hash TEXT存 siro-skill-package-v1:<sha256>：排序、明確length framing、相對UTF-8 path、每檔bytes與executable bits。含manifest、I/O schemas、所有module/data/dependency metadata。root另綁既有path_ref，同内容换root不能借批准。

Canonical root與所有directory/file以no-follow handles捕捉，拒絕symlink/hardlink/nonregular、escaping schemas、缺entrypoint source及已知bytecode/native副檔名。普通__pycache__不hash、不交付。最多512files／1024entries／32層／4MiB每檔／16MiB總bytes；不是通用dependency resolver或任意binary偵測器。

install只接受與實際內容完全一致的caller，預設disabled；enable重驗原批准hash/root，不能順便批准變更。legacy64hex rows原样保留，但is_enabled false、enable明示verification/approval；沒有migration／自動升級、清rows或操作live DB。只有既有可信owner明確install/enable可重批。

Dispatcher初查完整enabled identity、off-loop捕捉並核對caller manifest/schema/hash/root，以同一批bytes建立私有owned snapshot，来源准备期间变化拒绝；handoff後原source變更不能替換frozen approved bytes。交付前再查撤銷，worker收到已驗copy，不是原mutable root。最多8份active/preparing snapshot，候位取消不建copy；完成/失敗/取消（包括重複取消、thread join）清理。清理途中取消仍回CancelledError，不能復活成功。

原WorkerSupervisor semaphore加完整package hash到key，同id/version重新批准時不繼承舊concurrency。其餘bwrap mounts／network denied／clean env／CPU/memory/output/timeout/cancel保持。這是局部identity/resource修復，不新增scheduler/registry/background owner、runtime skill catalog或autogeneration pipeline。

## 驗收

| 驗證 | 結果 | 限定 |
|---|---|---|
| Exact pre-card source的新43 cases | 42 FAIL／1 PASS，3.11s | 核對三source SHA；部分新增API反例在原碼缺helper，主要換碼／換root／legacy authority反例獨立證明行为違反 |
| 原skill tests修前 | 5 PASS／4.12s | 原green未覆蓋package identity缺口 |
| 最終specialized＋adjacent | 66 PASS／3既有warnings，5.99s | 43新＋5原skill＋18procedural/catalog；非額外相加完成數 |
| 真Linux bwrap | PASS | 原network/hostfile/secret-env、CPU/memory/output/timeout/cancel/concurrency與frozen原碼/helper正向fixture；host marker與request皆合成 |
| Cleanup cancel／snapshot cap／concurrency反例 | 修前各1 FAIL→通過 | 當次候選發現取消復活、9>8copies；既有same-id/version stale semaphore peak2>批准1；保留三份RED log |
| 最終完整離線 | 906 PASS／5real_provider未選／3既有warnings，113.93s | 原RI-002／browser／voice/session／FIX-008/009保留；不是全產品／真人驗收 |
| format/lint/mypy/schema | PASS；223格式檔／213my py來源 | 無deps/locks、HTTP/WS或DB schema变动 |
| 精確4檔temp回退重套 | SHA PASS | 3production＋1新test，原test_skill_registry.py未改；沒有HEAD reset/live restore |
| 來源保存 | 227existing中只3production變動 | 前序卡與聲線／session hash不變；未讀私人聊天/WAV/key或重啟8026 |
| Scoped secret scan | 0finding | 合成fixtures only |

904與905兩份中間全套PASS保留，因後續實際反例修復已由906最終結果取代，不能當最後source證據或相加。初次mypy偵測test對imported alias的非export引用，僅改test引用；初次line長度已修，未放寬checker。修後第二agent不可用，root完成source/caller review，不宣稱獨立post-agent驗收。[source review與限制](source-review.json)。

## 風險與保留gate

FIX-007局部approved identity gate解除；**任意生成skill的接入仍需RI-003真隔離/可信checks、來源/review/明確enable**，沒有自動執行或發布。direct WorkerSupervisor仍是既有trusted內部/test入口，沒有把它變成對model公開的授權API。

Fingerprint不簽整個host Python/venv/OS，不認證所有import collision或敵意same-UID修改；snapshot也不保證被敵意host filesystem永久阻塞的thread有wall-clock取消上限。準備CPU/RAM/latency SLO未量測；8 slots限同一Dispatcher的copies，不是任意多实例的global quota。大量批准version/hash的semaphore idle retention為TECH_DEBT，沒有OOM證據、不造cache manager。這些限制不能藉full-mode或fixturePASS解除無review的generated-code gate。

FIX-002有用搜尋、FIX-005語音延遲／人耳、FIX-006自身理解仍未完成；release launcher／資料保留gate獨立存在。不重做已完成RT、不重新設計SIRO。

## 回退

先停止新增dispatch、取消/收束owned workers，再對匹配after SHA的精確[repair.patch](repair.patch) reverse-check/reverse。保存package/rows/approval evidence，不downgrade/覆寫DB；舊binary的id/version boolean不能被當新hash或legacy批准的安全fallback。只用temp演練，恢复后維持技能dispatch停用。[rollback](rollback.json)、[preservation](preservation.json)。

[baseline](baseline.json)、[checks](checks.json)、[最終回歸](full-suite.log)、[專項](tests-after.log)、[scanner](secret-scan.json)。下一張FIX-006：沿既有run owner提供可追溯自身故障context，先合成與真配置模型驗收；不增加全知記憶/新registry或繞驗證能力。
