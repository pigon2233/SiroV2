# Compatibility plan

## 2026-10-14 — FIX-020 / D56 release approval boundary

原 v1 source encoding 已證有歧義，不能保留其 execution authority。歷史 v1／None manifest 仍可 parse/read/serialize，v1 canonical payload/hash 固定語意不改；stage/launch/rollback 必須明確 v2 新批准，既有拒絕 status、CLI shape、schema/owner/data retention 保持。沒有自動 receipt 改寫、重新簽署或演算法猜測；新批准使用新 immutable version，不能同版覆寫。這是明示最小安全相容更正，不影響 default 非 signed launcher、Gateway、DB、provider 或 UI。[證據與限制](../evidence/FIX-020-2026-10-14/REPORT.md)。

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

Defaultproductlauncher execv/model/resource流程、defaultGateway main/create_app/healthready{state}、existingCLI stage/rollback、complete manifest wire保留。Opt-in才有typedVerifiedRelease與healthready release version/digest；startup/drain不回readyidentity。

Originalcwd、absolutecaptureddata、relativeassets仍同一root；fresh-I/-B selectedsrc、execenvcopy剔signingkey，wrongsource/ABI/tamper無installedfallback。D52sameactualschema only；candidate migration count不同/DBschema選後變動先拒，不依簽署range猜可以migrate。

273baseline中270不改；exact7 source-only disposable reverse/reapply PASS，保所有資料與Git歷史。D48 schema helper抽出前後AST相同；D51 backup/CLI四檔與D50 owner/operations source保持。

RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

Public backup_to(destination)、成功raw/ZIP格式、原CLI參數/result與既有ownedloopfactory保持；private _backup_sync(destination, cancelled=None)仍相容single-argument caller。ThreadEvent不新增permission/schema或provider/device耦合。

CLI temporary main-thread SIGINT只包此backup，exactprevioushandler於finally恢復；plainCancelledError及primarytypederror保持，signal cancellation/late flag→原KeyboardInterrupt/130。Backgroundthread不改OShandler； 其他 commands和D50 main不變。

raw final publication後取消仍保成果，不能將130解讀為rollback；原D49 restore全部bytes保持。269/271既有baseline bytes保持，exact4 source-only temporary reverse/reapply PASS；保留所有資料與Git歷史，source rollback不授權再用舊危險取消路徑。

[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。

> 2026-10-01 狀態說明：下列「尚未實作／僅設計」為 Phase 2 原始設計時點。當前逐卡完成與修正狀態以 RUNTIME_EVOLUTION_ROADMAP.md 及對應 evidence 為準。
設計，不代表已實作。原 T00–T40、既有未提交修改及 Phase 1 snapshot 保留。

| 邊界 | 相容要求 | 允許的增量 | Gate |
|---|---|---|---|
| HTTP/WS | 保留現有 URL、payload 必填欄位、事件種類與 terminal 語義 | optional run metadata；舊前端可忽略 | 舊 request/event fixtures + main 組裝 smoke |
| ModelRequest | prompt positional callers 仍有效 | optional messages；adapter fallback | 舊 prompt/new message 契約雙跑 |
| tool executors | 舊 arguments-only handler 可執行 | context-aware wrapper、結果 envelope | 正常/錯誤/denied/cancel parity |
| authorization | 保留 full 自動授權及 tools switch | execution facade 傳遞 policy decision | full/disabled/hash mismatch 一致；不新增逐步確認 |
| SQLite | 不改 001–012，不刪/改名舊欄位或 enum | 下一號 additive migration；先檢查實際最新號 | 空 DB、10→12→新 schema、12→新 schema、重跑/idempotence |
| identity/affect/relationship | immutable core、來源、revision、演算法保持 | context wrapper 只讀既有結果 | 固定 fixture state 值/事件一致 |
| audio/body | reference v1、body intent、既有 render 返回 bytes | worker 私有協定 request id / close | 畫面、取消、音色人工與 audio format 驗證 |
| configuration | 舊 env 優先序保留；不自動啟用雲端 | 新 runtime profile optional；缺省 legacy | effective-config 去密鑰快照比較 |
| Rust RPC | 現有 scope/grant/hash/socket 不變 | Python facade adapter | Rust 對等契約與故障隔離 |

## Feature profile

提議新增 `SIRO_RUNTIME_PROFILE=legacy|candidate`，缺省 legacy；尚不存在。profile 在 run 建立時固定，不能途中切換工具實作。細項測試 switches 屬候選內部配置，不開放任意不相容組合；例如 durable recovery 必須搭配 native message journal。

部署到 candidate 前：先合成測試，再隔離資料目錄，最後 owner product session。UI 繼續使用同一入口；只在診斷顯示 runtime version，不把實作細節放進日常對話。

## 資料與回滾

- 修改前一致 SQLite backup、integrity check，記錄 code digest、schema version、feature profile；不得在未知副作用仍執行時切換 runtime。
- first rollback 為 drain candidate、終止所屬可取消 child、將 unresolved action 標 unknown，再讓新 run 用 legacy。禁止讓 legacy 接續 candidate 的中途 run。
- additive schema 的舊程式可否啟動要實测，不能假設。若舊 loader 拒絕未識別 migration，使用已測過的相容版本或保留新 binary 關閉 feature。
- 備份還原只作最後復原途徑；會丟失備份後資料，必須停止寫入、保存新資料快照並安排匯出/合併，不以自動還原掩蓋資料遺失。
- 原始私人訊息/音檔/key 不進 evidence；用合成內容、結構統計、error code 與必要去識別摘要。

## 不變更區

Live2D SDK/assets、firmware、identity core、既有 migrations、Rust wire protocol、模型權重/聲音 reference、原 T 任務文件。個別 blocking issue 另列精確 scope，不能借 RT 卡做整體重構。
