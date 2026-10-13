# Runtime Intelligence — 本輪交付與驗證

日期：2026-10-09，Asia/Taipei。**完成現況核對與第一個開發期低風險切片RI-001；未交付自主skill generation、自我部署或完整產品發布。** 既有文字／語音／Live2D／RT成果與未提交內容保留。

## 五項文件產出

| 需求 | 唯一主要文件 |
|---|---|
| Current Architecture Audit | [CURRENT_ARCHITECTURE_AUDIT](../../runtime-evolution/CURRENT_ARCHITECTURE_AUDIT.md)，真入口、call chains、drift與gate；[ARCHITECTURE_REVIEW](../../runtime-evolution/ARCHITECTURE_REVIEW.md)與[RISK_REGISTER](../../runtime-evolution/RISK_REGISTER.md)同步 |
| T1–T40 Implementation Matrix | 更新既有 [ROADMAP_RECONCILIATION](../../runtime-evolution/ROADMAP_RECONCILIATION.md)，40項逐列source/tests/deps/risk/狀態；不再建重複矩陣 |
| Codebase Memory Integration Report | [CODEBASE_MEMORY_INTEGRATION_REPORT](../../runtime-evolution/CODEBASE_MEMORY_INTEGRATION_REPORT.md)，固定版、安裝、配置、索引、實測查詢、限制與維護 |
| Runtime Intelligence Design | [RUNTIME_INTELLIGENCE_DESIGN](../../runtime-evolution/RUNTIME_INTELLIGENCE_DESIGN.md)，沿用既有catalog/registry/worker/Policy，明示最小接口、候選、安全／批准／回退 |
| Incremental Roadmap | 更新既有 [RUNTIME_EVOLUTION_ROADMAP](../../runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md)：P0–P3與RI-001–006小卡；原T／RT歷史保留；[FIX_REGISTER](../../runtime-evolution/FIX_REGISTER.md)新增007–009局部修復定義 |

T01–T40：8項限定元件Implemented and Verified、4項Implemented but Unverified、25項Partially Implemented、3項Planned Only。這不是產品完成百分比；歷史真機／目前離線fixture／尚缺的外部驗收各自列出。沒有將T35／T39／T40或已有RT重新捏造為完成／取消。

## Baseline與保留

[baseline.json](baseline.json)、[environment.json](environment.json)記錄repo／main／c1d2d41及原dirty list、目前Linux x86_64/Python/FastAPI/SQLite/Rust/Web Live2D開發環境與硬體metadata。開始時先查錯 `/health` 得404，改用實碼正式 `/health/live` 得200；沒有將錯路由當服務故障或啟動第二個owner。

[REGRESSION_BASELINE](../../runtime-evolution/REGRESSION_BASELINE.md)已加入本輪701項、開發工具隔離／stale／mutation與回退基線；原2026-09-30 migration failure保留為歷史，不再當成目前未修故障。

[preservation-and-rollback.json](preservation-and-rollback.json)：原251個tracked source/tests/依賴lock hash **零變**；未提交003／004／005 source與既有untracked檔保留。沒有讀私人對話、DB、key、reference WAV、未追蹤使用者WAV內容；沒有停啟8026、呼叫私人對話endpoint或新的GPU／cloud推論。health／首頁／Live2D mount HTTP200，只證HTTP readiness，不等同本輪人眼／真人互動驗收。

## 實作範圍

- 新增受限開發helper、固定binary的TOML lock、project MCP設定、.cbmignore及developer-tools ignore；沒有增加production API／schema／Runtime framework／memory DB／router／worker。
- 手動安裝v0.11.0 linux-amd64 checksum已核對的binary與license；沒有執行上游installer／update或全域hooks安裝。公開checksum在TOML明示allowlist註解，不是credentials；獨立secret scan無finding。
- Git source-only projection、private/ignore/deps/symlink排除、bounded size、啟動前stale拒絕、single developer session、clean env、真Linux無網路namespace與只讀source/release。這不是production PatchVerifier的隔離修復。
- 更新audit/capability/matrix/design/review/risk/roadmap；清除native messages／catalog／session memory／summary／Rust／idle organizer的過期文件結論，保留原有效實作。

## 實際驗證

[checks.json](checks.json)與下列原始紀錄可重現；數量不可重複相加。

| 驗證 | 結果／限制 |
|---|---|
| 修改前全套offline | [full-suite-before.log](full-suite-before.log)：671 passed／5 real_provider未選／3既有warnings，156.91s |
| 修改後全套offline | [full-suite-after.log](full-suite-after.log)：701 passed／5 real_provider未選／3既有warnings；耗時以最後log為準 |
| 新developer tool負面與相容fixtures | [developer-tool-tests.log](developer-tool-tests.log)：30 passed；排除／symlink／actual-byte budgets／修改新增刪除stale／缺sandbox／env不繼承 |
| 真OS隔離 | [developer-isolation.json](developer-isolation.json)：12項PASS；host合成marker/home不可見、source/release EROFS、network ENETUNREACH、只有cache可寫；exact helper起訖hash一致 |
| lint／format／types／schemas | [format.log](format.log)、[lint.log](lint.log)、[types.log](types.log)：Ruff269 files／mypy204；export_schemas --check exit0 |
| Rust | cargo test --workspace --locked：6 library tests PASS（0.08s）；binary/doc tests0；不是新硬體或全部PC路徑Rust驗收 |
| MCP actual protocol | [discovery](mcp-discovery.json)及[query/call chains](mcp-callchains.json)：initialize/tools/list/真graph查詢成功；analysis拒index_repository、Cypher拒DELETE；[錯名更正](mcp-terminal-correction.json)保留一次function-not-found與更正查詢成功 |
| Code graph與資源 | [index.json](index.json)＋[index-resource.log](index-resource.log)為最後數量／single-run wall time與RSS；不是p95。來源manifest在私有developer-tools，未把索引cache提交 |
| 程式保留／回滾 | [preservation-and-rollback](preservation-and-rollback.json)：開發server停用／恢復由Codex list實際確認，config SHA相同；[developer-source-rollback](developer-source-rollback.json)：6個developer檔在temp reverse/reapply、原gitignore及精確SHA復原；沒有git reset原dirty tree |
| 新檔secret檢查 | [developer-secret-scan.json](developer-secret-scan.json)：僅本輪開發source／config／lock；結果空。未聲稱掃描私人資料或整個repo的發布secret gate已通過 |

另兩組140項盤點子集、40項安全元件回歸與四類安全反例見 [RI architecture REPORT](../RI-architecture-2026-10-09/REPORT.md)及矩陣。這些與701重疊；反例重現成功代表缺口存在，**不是安全修復PASS**。

## 已發現與後續gate

- FIX-007：技能hash不含plugin碼／deps，dispatch未綁批准的完整package；REQUIRED_FIX／HIGH／PLANNED。
- FIX-008：protected deletion漏過+++ path parser；REQUIRED_FIX／HIGH／PLANNED。
- FIX-009：release signature未綁schema bounds；REQUIRED_FIX／HIGH／PLANNED。
- OS untrusted-check隔離、真正launcher activation與保留最新資料的code rollback，仍為各自接入gate；不靠新增wrapper或「全部安全」旗標解禁。
- Core→services imports與module兩跳互import查詢無結果；call graph的3個SCC已對照callback／fetch injection／工具continuation，沒有據此刪dead code或推翻現架構。圖譜依然是best effort。
- Codex workspace server配置可讀；本輪active chat catalog尚未reload，nested Git project trust未改。這與本機MCP protocol成功不同。

正式自主流程仍為Analysis→Proposal→Isolated Implementation→Testing→Review→Approval→Deployment→Monitoring→Rollback；目前只允許可審核提案。人工部署／安全政策／permissions批准保留。Codebase Knowledge／Agent Memory／Runtime State不合併。

## 未驗證與接續

未跑本輪real-provider/GPU／人耳聽測／真人WebGL動作／ESP32／真HA／第二節點／24h soak／遠端CI／attestation。既有FIX-005首播速度及人工語意仍PARTIAL，FIX-002搜尋與FIX-006理解仍未完成。沒有將開發工具成功包裝成女兒自主能力或正式產品完成。

下一個低風險功能切片可按RI-002從現有ToolCatalog做唯讀metadata；產品品質沿原FIX卡改善。生成skill／自動patch checks／release promotion必須先解對應007–009與OS／人工／資料回退gate；原RT-011／013／015既有交付不重做。授權軟體逆向、任意CLI探索與自動部署不在本輪施工範圍。
