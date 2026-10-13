# D52 final source boundary review

2026-10-13（Asia/Taipei）。Independent subagent；production/tests 唯讀。ROOT 實作3 existing source，本 review僅新增boundary evidence。沒有live8026／privateDB/config/key/chat/audio/models/GPU或正式服務操作。

## Result

在下列 frozen source 及 D52限定profile，**沒有找到已確認、需要立即修復的 implementation defect**。這是source review＋direct public DTO/真temp SQLite負向檢查，不是任意release安全批准，也不替代root的full regression或另一agent的真正雙版HTTP。

| File | Reviewed SHA256 |
|---|---|
| `src/siro/core/releases.py` | `0937b3b11b816e16fd7fa9876efc353e0cd64e91bc361bc9f3c71555920ce98b` |
| `scripts/launch_companion.py` | `fcfcf6072cb2078fbf9529644c7ee0a4937e81afd648b6499198cbb271b49790` |
| `src/siro/services/presentation/gateway.py` | `5d4de5e5ac458a0cde7ed1252eef99d352a6c8f8c681977bd2bf371a62b4d4d3` |

## Findings and invariants

- **D48 behavior preserved.** 原 `_rollback_schema`完整body以 `self._schema→maximum`、`self._database→database`標準AST參數綁定後，與抽出的 `_read_data_schema` body完全相等；wrapper只委派，同一SQL、prefix/cap/type檢查、readonly/query_only、connection finally close及None語意。原rollback不新增launch/data migration，未改latest-data retention。
- **Existing default caller preserved.** 未選 SIRO_RELEASE_ROOT時 `_selected_release`不讀key/DB，原launcher配置/assets流程與execv保留。Gateway defaultmain仍以原2 positional args進 `_run_gateway`、原D50 owner包住startup/serve/drain；health.default仍原 `{state}`。未重造owner/updater。
- **Actual loaded source assertion.** signed exec為fresh `-I -B -c`，先插selectedsrc再import SIRO。Gateway在existingowner內以package/Core/Gateway各自真 `__file__`核對selected canonicalpath，然後重讀actualschema；wrong origin、candidate migration count不同、selected後schema變動均在 `_run_gateway`前拒。沒有以 `siro.__version__`或envlabel冒充。
- **Data/assets continuity.** parent保持原projectcwd，data傳absolute，renderer/runtime等仍原資源語意。signed mode只用prepared assets，缺就拒，沒有cargo/renderer/tokenizer provisioning。這不把no-bytecode當readonly OSsandbox。
- **Key/error surface.** childenvironment副本移除專用SIRO_RELEASE_SIGNING_KEY；parent環境保留。bootstrapargv只含public directory/version/digest/schema，health只回version/digest。Typed launch refusal在launcher/main呈固定status，不回privatepath/key；legacy模型key需求與原model settingsallowlist不變。
- **Readiness follows startup.** 新release_started在全部startup/activation初始化後設True，finally先False；beforelifespan、startupfailure、afterdrain無release-readymetadata。Legacyboolean健康shape保留；signedready不是model／語音／renderer整體產品驗收。
- **Source/permission boundary.** DTO和read-onlyselection在既有Core release component；Gateway只composition/runtimevalidation及projection；無provider/tool/device互滲、policy bypass、自批准或globalreleasecontroller。

## Independent runtime controls

`boundary-runtime-probe.py`實際建立temporary SQLite並保留一筆合成latestdata。9 direct casesPASS：exact3origin/matchingactualschema，wrongpackage/Gateway/Core 3cases，candidatecount較多/較少2cases，actualschema新增／nonprefix／missingledger3cases。每次DB bytes保留，未新增WAL，最後合成value保留、temp root已移除，source起訖hash一致。完整原D48schema AST equivalencePASS。此probe的source-originpaths是direct DTO控制資料，沒有假裝真的import該fixture或啟child。

命令：`.venv/bin/python docs/evidence/RI-005-launcher-2026-10-13/boundary-runtime-probe.py` → exit0；結果 `boundary-runtime-result.json`。此script Ruff lint/format→PASS。初次evidence脚本有longline lintfailure，已僅格式化/縮短evidence文字後rerun；production無因此修改。

目前pytest原12caller＋70selector/root加DTO tests與truechildprobe由root及另一agent另記，不在此review冒稱已执行。

## Confirmed test gap addressed separately

首次檢查發現新pytest尚未覆蓋DTO validate_runtime wrong3origins／actualschemachanged／candidate migrationrefusal。已回報root；root明確承接永久cases至 `test_release_ready_identity.py`，此review另作上述9checks。這是TEST_GAP，未發現productionrootcause，不建立多餘FIX重構。

## Gates retained

Parentverifieddigest→childimport間sameUID package mutation/TOCTOU仍NOT_VERIFIED；origincheck不是livebyte cryptographic attestation。D50 CLOEXEC不會連續移交maintenancelease，first-adoption舊／非受管writer不參與lock，故oldwriterabsence／人工批准maintenance→runtimehandoff仍BLOCKED。sharedpinnedinterpreter/deps只接受D52-compatible src package；舊ABI/migrationprofilefailclosed，沒有fallback。generalarbitraryrelease/dependencies/OS/powerloss/正式deployment、FIX-002/005/006產品gates都保持。

本次沒有證據推翻originaldesign，不新增ARCHITECTURE_CORRECTION。未放行正式服務，不因有限sourcePASS降低RED zones。若root其後改source，必須按上表hash重新核對後才沿用這份review。
