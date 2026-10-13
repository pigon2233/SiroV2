# RI-005 D52 — signed launcher boundary review

2026-10-13（Asia/Taipei）。唯讀 source review；沒有啟動或接觸 8026、私人 DB/config/key/chat/audio/models/GPU，也沒有修改 production 或 tests。此文件提出可驗證的窄切片，不代表 release integration/deployment 通過。開始工作時 Git main 已含 FIX-015；既有未追蹤 evidence 保留。

## Confirmed caller and behavior

| Source | Current behavior | Consequence |
|---|---|---|
| `scripts/launch_companion.py:12–14,81–84` | 固定 project root/cwd，最後以現用 interpreter `import siro.services.presentation.gateway; main()` | 沒有消費 active release；`.env.local` 只有模型 allowlist，不能把未簽 release flags 混入該檔 |
| `scripts/start:21` | `uv run siro-gateway`，PID supervisor/graceful TERM 沿用 | 仍啟動現用環境，不是 signed release loader |
| `src/siro/operations.py:43–69` | installed user unit 的 ExecStart 為現用 Gateway executable，固定 data/log env，不會自行 start | 舊 unit 仍是可信既有入口；D52 未接它不能宣稱全部部署入口接入 |
| `src/siro/core/releases.py:62–104` | stage/copy/check/reverify 後寫 immutable-version directory、完整 `manifests/<version>.json` 與 `active.json` | pointer 是意向，非 running-process identity；existing healthcheck subprocess success 也不是產品 readiness |
| `src/siro/core/releases.py:167–231` | bounded unique-field receipt parser、readonly actual-schema snapshot、完整 manifest signing verification 已有 | resolver 應重用；不建立第二套 updater/signature/schema/lock manager |
| `src/siro/services/presentation/gateway.py:1333–1345` | main 在 `_run_gateway` 之前取得既有 canonical DB owner | 新 caller 不得 bypass；其實際啟動/serve/drain IO 仍需受該 owner 約束 |
| `src/siro/services/presentation/gateway.py:546–555,625–627` | lifespan await startup 與 activation init，ready 回 core state；初始 state 已是 healthy | 現有 response 不含版本；新增 release identity 要在 startup 完成後才標 ready，不能以 default healthy 冒充啟動成功 |
| `src/siro/__init__.py:3–8` | `__version__` 來自 interpreter 已安裝 dist metadata | shared interpreter 下可能永遠 `0.1.0.dev0`；不可當 selected release semver |

以上行號為本 review 開始時的 source，root 後續 D52 改動可能移動行號。沒有依賴遠端文件或新增 SDK。

## Smallest implementable slice

1. 在既有 `ReleaseManager` 增加一個唯讀 active resolution 方法，回 frozen record（manifest version、source_sha256、canonical bundle path、schema bounds）。具體名稱由 root 契約決定。它讀 bounded/duplicate-reject `active.json`，嚴格 semver 先於 path lookup，再讀相符 version 的完整 signed stored manifest，檢查實際 target digest 及 source/record aliases；schema 未知或不相容即拒絕。沒有 stage、rollback、backup、migration、healthcheck 或 execute 副作用。
2. 正式 launcher 的 opt-in signed mode 才呼叫 resolver。原未選 signed mode 的模型/Live2D/tokenizer/Rust readiness 與 allowlisted settings 邏輯保留；不靜默退回 working tree。選定 release 的必要 source entry（`src/siro/__init__.py`、Gateway）缺失直接拒絕，不能從 editable install 補缺。
3. child 啟動必須真的由 selected `src` 匯入。單改環境變數 `SIRO_RELEASE_VERSION` 或 parent JSON 不是證據。最小 bootstrap 能把 selected `src` 固定於首位，確實檢查 imported `siro` 和 Gateway `__file__` canonical origins 在該 signed source；再進既有 Gateway main。不要以 shared `importlib.metadata.version()` 推斷。
4. Gateway composition 只持有 immutable、白名單 release identity（version + source_sha256 + identity kind）。可加 optional identity 到既有 `create_app`/readiness callback；Core 不 import launcher/OS driver。未選 release 時健康 JSON 舊 shape 保留。release mode response 必須是 process 內實際 source 驗證與 lifespan 成功後的 identity，不洩露本機路徑、key、env、config。
5. D52 可先解除唯讀 resolution／限定 profile actual source identity／readiness 的局部 gate；人工 maintenance approval、first-adoption 舊 writer、maintenance→runtime handoff 是下一個窄切片，不以本卡 PASS 解鎖正式服務切換。

## Compatibility and failure fences

- **Data directory 必須固定。** 原 Gateway `SIRO_DATA_DIR` 可為相對值、預設 `.siro-data`。若改 cwd 到 release 而未 capture 原入口相同的絕對 data path，会在每版 release 內新建不同 DB；code rollback 看似忘記記憶。caller 先 resolve 原 data/resource paths，維持同一 latest DB 與 log，不能在 release root 放私人資料。
- **Signed bundle 不得被 import/build 改寫。** `_digest` 涵蓋所有 files；Python `__pycache__` 会使 hash 改變。child 使用 `-B`/等效 no-bytecode，必須證明 before/after bundle digest 相同。existing Rust build、Live2D repair、tokenizer provisioning 保持在原資源位置，不能偷偷寫入 signed tree 或下載新 dependencies。預先未準備資源就明報，不在此卡擴 updater。
- **No fallback/import blending.** stale editable installation、污染 `PYTHONPATH`、cwd 的另一 `siro` 不可勝過 selected src。必要 package/module origin檢查與 wrong-version fixture 要 FAIL，不可只測 argv label。
- **No approval invention.** signing key/complete signed receipt 是 integrity evidence，not a new approval workflow；本卡不接模型自批、任意輸入包、未知健康命令自動執行。若需要 explicit expected-version/hash，必須由 trusted caller輸入，mismatch zero effects。
- **Same-UID hostile write 不在本 profile 裡。** 路徑 canonical/reverify 防 static aliases，但不是包 readonlyness 或 hostile TOCTOU OS isolation；一般 untrusted signed code也不是安全沙箱。必須保留 limitation。
- **O_CLOEXEC lease 不等於 exec handoff。** D50 owner FD 在 exec 關閉，child 稍後再取可有空窗。managed writer 同時仍會被 child owner 拒，但不能把 parent preflight + child main 當持續 maintenance lease transfer；first-adoption 舊版根本不合作。此次隔離 temp DB actual launch可驗，正式 switch 仍 BLOCKED。
- **Existing healthcheck success 不等於真模型/voice/renderer驗收。** readiness此卡只證 signed source identity 與 application startup，FIX-002/005/006 產品 gates保持。

## Meaningful test design

### Resolver controlled/real-filesystem cases

完整 signed 1.0.0/2.0.0 fixture；active pointer exact fields/semver/path traversal/duplicate field/non-dict/oversized JSON；missing receipt、legacy signing format、wrong signature、signature不含改後bounds、version mismatch、bundle mutation、symlink/hardlink source/record；actual temp SQLite prefix schema未知/相容/不相容；拒絕時 source/data/pointer/receipts unchanged、healthcheck/exec/backup/migration零呼叫。原 release/signing/retention cases都保持。

### Launcher controlled cases

原未設定模型/unsupported token budget三個tests unchanged；opt-in resolver只呼叫一次、失敗 zero exec/no fallback；selected src/cwd 實際可查且absolute data/resource path unchanged；不繼承錯誤 release label；no-bytecode flag；不打印 key。必要entry缺失拒絕而非從 installed package補。正常legacy argv/settings/permission語意保留。

### Actual child acceptance（synthetic source/data/provider）

在臨時根下建立兩個真 signed source包，其 source可查辨別 marker（不能只有env label）；以實際 launcher/bootstrap啟動真 HTTP ephemeral port，response 與 imported source marker/manifest hash一致、startup未完不ready、startup error不ready、SIGTERM後child joined與owner可再取。rollback只切codepointer，version2運行後新增SQLite row在啟動version1仍保留；完成-effect ledger無replay；第二writer拒絕；故意污染PYTHONPATH指向workingtree/另一包仍不混入。包在啟動/停止後hash不變且無__pycache__。不啟動live8026，不讀現用.env/key/database/模型，不用private聊天。不能以 fabricated callback當actual process PASS。

若 profile僅完整 SIRO src + shared pinned interpreter/deps，應如此明報；不推廣為任意wheel/依賴包、多OS/一般generatedrelease。

## New blockers / non-blockers

- 確认 MISSING_INTEGRATION：actual signed release消费與process identity目前沒有；用 D52 bounded task解決，非原整體設計錯誤。
- first-adoption舊／非受管writer、批准maintenance/handoff、正式服務deploy仍是原 blockers，不需要臨時新 abstraction。
- schema snapshot要求actualdata與owner协调；僅resolver readonly不會證全程writer停止。
- 現有stage healthcheck與 `_backup_database` 其他 lifecycle風險不屬此接線切片；不要因看見不同scope而重構全release subsystem。
- 本 review 沒有執行 tests／child／rollback；不得作 PASS。root實作後應再作凍結source獨立review。

## Root proposed D52 profile review

Root proposed `ReleaseManager.resolve_launch_target` → opt-in `SIRO_RELEASE_ROOT` companion launcher → fresh `python -B -c` bootstrap → actual origin checks → Gateway `main(optional frozen identity)` → ready metadata after lifespan startup. 此範圍符合最小修復；舊mode exact health shape、existing assets流程、D50 owner保留，沒有新 updater。

可再縮小 cwd 風險：保持 original launcher project cwd，只把 selected canonical absolute `src` 插入 child `sys.path[0]`。如此既有 relative data/workspace/log/voice/reference/renderer語意全部保持，不需要新全面path manager；data仍capture絕對值可作防禦。Bootstrap在selected `src` 插入與 `siro` 匯入前，不得先import current environment `siro`/Core，以免 `sys.modules` 留舊source。Freshprocess source checks至少含 `siro.__file__`、Gateway `__file__`、`core.releases.__file__`，不可只有 Gateway一檔label。

使用 `execve` 的environment副本移除專用release signing key，比永久 `os.environ.pop` 更容易證明失敗時原caller保留；legacy path可保留既有execv。模型連線key仍是原模型需求，不打印。D52包需要新main參數，是明示相容profile；unsupported old package failclosed，不能把錯誤當legacy fallback。

Reverify parent snapshot與 child來源path只能證靜態/正常協作profile；same-UID在verify後改包的 race不是origin check能解決。若本卡沒有真正readonly/OS isolation/frozen source delivery，不宣稱這個gate解除，亦不為它再建第二hash/loadermanager。實際HTTPready的version/hash應來自已核對 source的immutableidentity；回應不包含root/sourcefile實體path。
