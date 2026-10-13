# Codebase Memory Integration Report

日期：2026-10-09（Asia/Taipei）。**開發期整合已實作及本機 MCP protocol 驗證；沒有接入 SIRO production runtime／Agent Memory。** 本輪來源基準 main / c1d2d41b2afc8844ff46f328043f7d2e8bf3cabe 加既有 dirty tree。五份產出入口及實跑證據見 [本輪 REPORT](../evidence/runtime-intelligence-2026-10-09/REPORT.md)。

## 安裝與來源核對

| 項目 | 已確認狀態 |
|---|---|
| 官方專案／固定版本 | [DeusData/codebase-memory-mcp v0.11.0](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0)，2026-09-15發布；source commit 8972ea69c6ad94b1ef1d4ffbf0a92d78d2db1798 |
| 平台 | 本機 Linux x86_64；選 linux-amd64 archive；不是其他OS已驗 |
| Archive SHA256 | 032b33c1833919a2d1de67ff6367fa6ea46aee8689c86ef223c88fae3b6e4536；下載物與官方 release API digest、checksums.txt 三方一致 |
| Executable SHA256 | a831cdcafaed7b1f7c23ce996a72a035f2188d7e20e9a18f39ec4b2d4e3302a6；每次啟動由本機lock核對 |
| 授權 | MIT；保留 archive LICENSE／THIRD_PARTY_NOTICES.md。此處只作本機開發工具，未打包或宣稱第三方資產可隨產品重新散布 |
| Provenance | checksum verified；GitHub attestation／Sigstore **NOT_VERIFIED**。未為此另外安裝gh/cosign，不能稱provenance verified |
| 安裝方法 | 檢查固定版installer/source/docs與archive成員，拒絕absolute／..／symlink成員；手動複製binary與license到私有開發目錄；**未執行curl\|bash、install、update或廣泛修改client/hooks/skills** |
| Runtime dependencies | uv.lock／Cargo.lock／pyproject dependencies未改；獨立開發binary的版本及hash存 [codebase-memory.lock.toml](../../config/development/codebase-memory.lock.toml) |

已讀固定版 [README](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/README.md)、[Configuration](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/docs/CONFIGURATION.md)、[ignore規則](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/docs/cbmignore.md)、[Security](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/SECURITY.md)、installer及MCP/CLI/discovery/daemon相關source。沒有把main分支的17工具文件套用到固定版；**執行檔tools/list實際為analysis profile的13個工具**。

官方文件本身有漂移：固定版README稱無自動更新外連，SECURITY仍描述初始化的GitHub update thread；選取source沒有該初始化thread，不據此聲稱完整安全audit。本機launcher用真實無網路namespace限制，不依賴這項宣稱。README CLI例的 `--format json` 在實際binary的index tool不支援，已改用 `cli --help`／`cli index_repository --help` 確認的介面；另 `/project` 被原生broad-root guard拒絕，改為具體 `/workspace/projects/SiroV2`，未放寬guard。[設定試跑失敗與修正](../evidence/runtime-intelligence-2026-10-09/setup-iterations.json)不當成成功驗收。

## 配置位置與client驗證

- 本機binary、cache、投影、source manifest：`/home/jasonliao/文件/Siro/SiroV2/.siro-data/developer-tools/codebase-memory/0.11.0/`；Git ignore，不含私人runtime DB。
- 開發入口：[scripts/codebase_memory.py](../../scripts/codebase_memory.py)。只支援 `index`、`serve`、`config`、`version`；缺bubblewrap或hash不符即失敗，沒有直接host fallback。
- 目前已受信任的workspace MCP設定：`/home/jasonliao/文件/Siro/.codex/config.toml`，server `siro_codebase`，用 `/usr/bin/python3` 啟動repo helper。沒有修改既有全域config／其他MCP servers。
- Repo同名設定：[.codex/config.toml](../../.codex/config.toml)，供此checkout作受信任project時使用。**實際CLI測試：parent workspace可列到siro_codebase，直接在nested Git root執行未載入該project設定**；未偷偷更改全域trust。不能把兩處檔案存在等同兩個client都已連上。
- Codex CLI 0.159.2已支援MCP；[client-config.json](../evidence/runtime-intelligence-2026-10-09/client-config.json)保留實際列表。設定方式核對 [官方MCP文件](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。本輪現有chat tool catalog尚未重載，**未宣稱新工具已直接出現在本輪agent catalog**；需重載受信任workspace後另行確認，本輪未驗證顯示。這與下述本機protocol已實際呼叫成功分開記錄。
- Client allowlist限11個讀取工具；server用 `--tool-profile=analysis` 強制13個讀取工具，不可藉直接呼叫繞過mutation禁令。`compare_graphs`／`detect_changes`未在client開放，因目前只有一個無Git歷史的安全投影。

## 索引範圍與隔離

明確來源為 `/home/jasonliao/文件/Siro/SiroV2`，不是掃描home或整台電腦。由Git inventory選目前tracked及未忽略的untracked source，二次 `git check-ignore --no-index` 排除後來被ignore的tracked檔。

投影涵蓋src（Core/Memory/tools/provider/Gateway/WebSocket/Web UI）、runtime Rust、tests、scripts、schemas、firmware source、公開config examples與根建置metadata/README。只複製允許的原始碼與公開契約；沒有複製.git歷史／私人working data。每檔source SHA256保存在本機manifest，投影內的相對路徑對應repo原碼。大型licensed Cubism dist、模型與build output不索引，Live2D外部SDK呼叫鏈由現有mount/transport契約及直接source補核。

排除 `.siro-data`、.env真值、private credentials、音訊／圖片、private-key／access-token等命名、symlink、venv/deps/vendor/node_modules、generated/build/dist/target、舊docs/evidence source備份。Repo [.cbmignore](../../.cbmignore)提供手動維護的第二層排除，但本次真正執行的是更窄的source projection。公開 `config/models.example.env` 是刻意允許的設定範本，**寬泛 `.env` graph搜尋會命中它，這不是私人.env被索引**；精確private路徑查詢無命中。

helper在Linux bubblewrap內：只讀source/release、可寫獨立cache與private tmp；host home不可見；乾淨PATH/LANG，不繼承API keys；network／PID namespace分離。這是**本輪開發工具的隔離**，不等同既有PatchVerifier已修成sandbox。最多5000檔、單檔2MiB、總32MiB；CBM_WORKERS=2與CBM_MEM_BUDGET_MB=512是引擎設定，**不是OS硬性CPU／RAM cgroup上限**。單一開發session lease拒絕同時index/serve，避免cache與投影競爭。

每次index/serve先設 `auto_index=false`、`auto_watch=false`、`watcher_enabled=false`、`ui_enabled=false`；沒有開啟持續監看／自動同步或UI port。讀取模式只使用既有cache。`serve`啟動前比對source manifest，來源新增／刪除／變動就拒絕；**已連線session仍是該版本快照，不持續監看原碼**，改碼後應斷開開發MCP、手動重索引、再連線，不能當live truth。

## 已執行結果

最後一次 `python3 scripts/codebase_memory.py index`：**exit0，250檔／1,516,720 bytes source，3,092 nodes／16,700 edges，status indexed，expected counts一致；partial/unusable/missing counters為0**。8條重點路徑coverage顯示metadata_match/no_recorded_issue，但工具明示best_effort，不能推導語意完整。[index.json](../evidence/runtime-intelligence-2026-10-09/index.json)。

一次整體index（含4次設定程序與投影）21.68秒、peak RSS312968KiB；一次stdio初始化19.804秒；範例schema/查詢約0.01–0.06秒。這些是**單次本機樣本，非p95或產品對話效能**。目前足以採手動開發索引，不據此啟用watcher或放進常駐SIRO。所有protocol probes關閉stdin後exit0，最後無遺留codebase程序。[resource](../evidence/runtime-intelligence-2026-10-09/index-resource.log)、[cleanup](../evidence/runtime-intelligence-2026-10-09/process-cleanup.json)。

真正的本機stdio JSON-RPC client已執行initialize→notifications/initialized→tools/list→tools/call，不是只檢查config檔。原始請求／回覆：[discovery](../evidence/runtime-intelligence-2026-10-09/mcp-discovery.json)、[analysis](../evidence/runtime-intelligence-2026-10-09/mcp-analysis.json)、[callchains](../evidence/runtime-intelligence-2026-10-09/mcp-callchains.json)、[terminal correction](../evidence/runtime-intelligence-2026-10-09/mcp-terminal-correction.json)。

| 查詢／分析 | 實際觀察與直接source核對 |
|---|---|
| list_projects／get_graph_schema／get_architecture | 一個SiroV2投影；250File、214Python files等；辨識Gateway、IntegratedCompanion、SQLite、Rust、HTML與路由。入口由launch_companion.py／gateway.main再核，不將每個test入口當產品service |
| 使用者訊息 | trace IntegratedCompanion.respond→CompanionCore/ConversationEngine、event/journal、memory/body callbacks；完整HTTP→model→delta/terminal由[現況call chain](CURRENT_ARCHITECTURE_AUDIT.md)補上。深度2／45-row查詢有分頁限制，不稱完整coverage |
| 模型工具 | ToolOrchestrator.execute→catalog.require／proposal owner／transition／ExecutionContext；具體executor由main動態註冊，graph沒追出closure不表示不存在。已有工具結果continuation與取消fixtures支持 |
| 記憶 | ingest_owner_request→remember/recall→MemoryRepository ports；額外trace真SQLiteMemoryRepository.add/search→SQLiteStore.run_transaction，核對main注入及scope/revision。不能把graph當Agent Memory |
| runtime錯誤 | 首次錯用 `_finish_agent` 得function not found；保留失敗，經source及search_graph更正為 `_finish_candidate` 後trace成功，顯示cancel_run／discard／journal terminal。不把查詢錯名當SIRO缺模組 |
| Live2D | MinimalWebBodyAdapter.set_emotion→_send→BodyTransport.send；實際WebSocketBodyTransport排隊／單writer→/ws/body→licensed Web renderer由直接source補核；HTTP200僅readiness，本輪未做人眼動作驗收 |
| 影響分析 | ToolCatalog.require inbound追到ToolOrchestrator.propose/execute與IntegratedCompanion._propose_tool_calls；metadata變更須保這些舊契約。SQLiteStore.run_transaction fan-in90包含tests，不等同production負載熱點 |
| 層與循環 | Core→services IMPORTS查詢、Module兩跳互import均0；直接import邊界測試及rg補核。不能稱全系統不存在循環 |
| 寫入拒絕 | analysis profile直接呼叫index_repository被拒；query_graph DELETE被拒，graph counts未因此變動。不以工具從清單消失代替拒絕驗收 |

圖譜cycles查到3個**call SCC，非import循環結論**：`request↔authorizedFetch`對照index.html:127–152為注入fetcher與wrapper，沒有request呼叫authorizedFetch，是推導誤判；`connectControl↔renderToolProposal`是onmessage與使用者onclick回呼；`continue_after_tool↔_propose_tool_calls`是既有工具續跑，受run/step/terminal條件控制。未因此刪碼、合併模組或添加新scheduler。動態注入／callback／接口實作仍需人工和測試；未以dead-code搜尋取消原task。

## 維護與回滾

日常從repo root執行：

```bash
python3 scripts/codebase_memory.py version
python3 scripts/codebase_memory.py config
# 先斷開開發MCP session；單一lease會拒絕與serve並行。
python3 scripts/codebase_memory.py index
```

native/OS條件缺失時明確失敗；繼續用rg／AST／現有測試查source，不安裝任意替代框架。升級前重新核對官方release/hash/license/介面/排除，更新獨立lock、停開發session、重建可丟棄graph並重跑隔離與查詢；不能默認自動更新。

全新主機復現：從lock的固定HTTPS URL下載archive及同版checksums，驗上表SHA，再檢查tar成員；僅複製binary/LICENSE/notices至上述release目錄、binary設0700。檢查bubblewrap可用後執行index。依新的絕對repo位置更新**project** MCP command/cwd；不要把此主機路徑當portable安裝器。官方attestation可另依SECURITY列出的gh attestation verify完成，未做不可標已驗。

回滾已實際演練：parent project server enabled=false→Codex list確定disabled→恢復原設定，SHA起訖一致；SIRO不需重啟。完整移除時只刪本輪開發helper/lock/tests/config entry/排除規則與developer-tools cache；保留原dirty changes與使用者資料。原251檔source/tests/依賴lock SHA完全一致，8026 health／首頁／Live2D mount HTTP200。[preservation-and-rollback.json](../evidence/runtime-intelligence-2026-10-09/preservation-and-rollback.json)。

未完成：active chat MCP catalog hot reload、attestation驗簽、其他OS、語意全覆蓋、watcher長時負載、真模型／人耳／真人Live2D／真硬體／24h／遠端CI。本輪沒有為這些宣稱PASS。
