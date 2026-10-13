# RI-004 — 固定清單技能候選與待審入口

日期：2026-10-10；基準 HEAD `c1d2d41` 的既有 dirty workspace，D44 先於本卡 source 修改。**RI-004 整體 PARTIAL；explicit-owner fixed-template → existing catalog check → package capture → real RI-003 verification → review/export 切片 VERIFIED**。沒有載入正式 8026 或部署。

## 交付與操作

candidate profile 的「電腦協助 → 學習新能力 → 準備待審技能」會準備 `markdown-checklist-v1`。用途為解析貼上的 Markdown 待辦清單；只接受 text，沒有檔案、網路、任意程式或依賴輸入。此入口目前準備技能，尚不能直接在對話呼叫該技能。

服務先查看同一 ToolCatalog 的全部 inventory，包含隱藏／不可用／unknown rows；固定 typed aliases 已存在就不生成、不驗證、不執行。`computer.execute` 若登錄則作一般替代來源提示，無 executor invocation。這是 exact typed-name check，**沒有宣稱語意缺能力或已搜尋 installed registry**。

固定 v1 package 只有 manifest.json/input.json/output.json/plugin.py；沿用 `capture_skill` 的 complete framed digest、既有 manifest/schema，沒有 host entrypoint import。權限空、observe/read_only/network denied、concurrency1。Parser 支援 -/*/+ 的空白/x/X checkbox、Unicode 與 triple-backtick/tilde fenced sections；UTF-8≤16KiB、≤256lines、≤128tasks、每項≤256chars。不是完整 Markdown parser。

外層臨時 workspace 只包含固定 package 與獨立 trusted tests。PatchProposal 僅新增 captured plugin bytes 到 `src/plugin.py`，以 RI-003 真 bubblewrap／stdlib synchronous unittest profile 驗六個 parser cases。Package JSON 不掛入沙箱；完整 package 靜態 capture 的結果、plugin/test/proposal SHA、proposal UUID、changed_paths 與 cleanup 綁成 review evidence。失敗／unsupported／報告不匹配永不成為 passed 候選。

Gateway 只傳輸與驗 token/origin/tools gate，候選 workflow 留在 composition service。單一 active owned job、busy409、offloop preparation/cleanup、取消及 shutdown 都 join；tools-off 停止 active job。UI 安全純文字呈現、手動匯出、無自動下載／network retry／reconnect replay；stale response fence 保留。任何 PASS 都維持 `trust_level=unreviewed`、`installed=false`、`enabled=false`、`authorizes_execution=false`、`approval_required=true`。沒有 approve/enable API。

## 證據

| 驗收 | 實際結果 | 證據 |
|---|---|---|
| 修前契約 | service21FAIL、frontend28FAIL、Gateway31FAIL；另 snapshot1FAIL（明示 synthetic types） | service-before.log／frontend-before.log／gateway-before.log |
| 最終新 tests | 88 cases：service23、Gateway32、frontend33；包含實際 OS candidate tests 與 actual service→page payload | new-tests-final.log |
| 相鄰隔離／skill package／frontend | 133PASS；此為較早 focused 檢查，不與 full 重複相加 | service-adjacent.log |
| 完整離線 | **1,127 PASS／5 real_provider 未選／3既有warnings／130.97s**；原1,039cases保留 | full-suite-final.log |
| 真產品鏈 | **23/23 PASS**：temporary Uvicorn、Chrome154、實際固定 profile bwrap、匯出、雙擊、busy／cancel／tools-off／cleanup；cancellation timing gate 為 synthetic | verify_product.py／product.json／product.log／review.png |
| 靜態 | 全 repo Ruff lint／format289；mypy224；schema export check；diff check PASS | lint-final.log／format-final.log／types-final.log／schemas-final.log |
| Secrets | exact6 source0；owned evidence286 recorded SHA/Git identity false positives，每項對 detector hash；unresolved0，all-files/no network verification | secrets-source.json／secrets-evidence.json／secrets-review.json |
| 保存／回退 | baseline248 中246不變，只有既有 Gateway/index 兩檔改動、四檔新增；temporary exact6 reverse/reapply SHA 完全一致 | preservation.json／rollback.json／repair.patch／verify_source.py |

完整 pre-card source projection 另存 `complete-tests-before-final.*`：原 Gateway/index SHA 匹配、新 service 不存在，collection return2／ImportError，**沒有功能測試執行**；不把它當88個失敗案例。初次 evidence harness 缺 public test helpers 的失敗保留在 before-projection-harness-first.log，修正 harness 後才驗預期 missing interface。

獨立 read-only audit 找到兩個局部 integration defect：catalog order 使 later general alternative 遺漏（1FAIL/1PASS→2PASS），service `rejected_report` 與 UI `binding_mismatch` 不一致。已 local repair、兩個 actual service→frontend case 驗 PASS／UUID mismatch，follow-up 無剩餘 confirmed scoped blocker。詳 source-review.md。

## Scope／相容與回退

只有既有 `src/siro/services/presentation/gateway.py`、static/index.html，新增 `services/tools/skill_candidates.py` 和三個 integration tests。Core、ports、procedural traces、registry/dispatcher/worker、LLM/TTS/Live2D、authorization defaults、SQLite schema、locks 全不變。Legacy 沒有候選 owner，入口503；metadata 為 additive，既有 control/model tools 不變。

回退 patch SHA `4fbf65169f537a14dd46f59cd5cd9d98b193c17951389d334ec3e26bc7491ce0`。演練只在 temporary source tree 撤本卡六檔，不撤前序 dirty 工作，不讀／回退 DB，不套 live patch。候選不持久化，頁面關閉後審查資料不恢復；owner 可在關閉前手動匯出。沒有私人聊天／DB／音訊／keys、8026重啟、模型／GPU／registry effects或正式部署。

## 限制與下一步

這是固定 builtin template；沒有 LLM 任意技能生成、repeated-work trace intake、skill security review、owner批准、registry install/enable、實際 worker執行或撤銷。命中 unavailable/unknown 並不證明另一工具不能完成目的；本卡不做語意推論。只認證既有 RI-003 Linux x86_64 CPython3.14 單程序 profile；不繼承成 worker／多程序／依賴／aggregate kernel RAM 證明。Candidate tests PASS 不是安全審查。

**KEEP RI-004，SPLIT 接入**：下一窄步驟先獨立驗固定低風險用途的實際 worker bytes／OS boundary／取消與權限，再做 package-bound explicit review/approval、版本拒絕與撤銷，最後接既有 catalog；不能用此 review PASS 直接啟用。RI-005 launcher／single-writer／latest-data rollback gate 保留。FIX-002有用搜尋、FIX-005延遲／人工聽驗、FIX-006理解仍各自PARTIAL；既有 RT-011/013/015 DONE不重做。
