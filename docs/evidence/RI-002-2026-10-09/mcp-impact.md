# RI-002 — 修改前呼叫與影響範圍

2026-10-09。本輪嘗試啟動開發期唯讀 MCP，但既有 owner 持有 session lease，回傳 exit 2／`Resource temporarily unavailable`。沒有停止 owner、繞過 lease 或重索引。依 root 指示，重用 RI-001 的既有 graph snapshot，並以本輪直接 source／AST 交叉核對；**不是本輪新 MCP query 成功**。

`orchestrator.py`、`integrated.py`、`gateway.py` 三檔的修改前 SHA-256 均與 RI-001 baseline 相同，且 source 核對期間沒有變更。完整 request／response、雜湊與 AST 接點在 [mcp-impact.json](mcp-impact.json)。沒有修改 production、script、test 或 config。

| 目標 | 直接 caller／資料去向 | RI-002 相容性要求 |
|---|---|---|
| `ToolCatalog.definitions` | `ToolOrchestrator.model_tools`，orchestrator.py:418 | 仍只提供 available、model-visible 的既有 ToolDefinition；保留名稱／schema 及 deepcopy。 |
| `ToolCatalog.snapshot` | `ToolOrchestrator.tool_status`，orchestrator.py:423 | metadata 為既有 snapshot 的相容擴充；不得因探索呼叫 executor。 |
| `ToolCatalog.require` | `propose`:485、`execute`:553、巢狀 `execute.invoke`:573 | 三個驗證接點都要保留；資料發現不授權，dispatch 前仍重驗 readiness／arguments。 |
| `ToolOrchestrator.model_tools` | `IntegratedCompanion._model_tools`，integrated.py:146 | candidate 沿用 catalog；legacy DEFAULT_MODEL_TOOLS／`_AGENT_TOOLS` 路徑保留。 |
| `ToolOrchestrator.tool_status` | Gateway `/v1/runtime`，gateway.py:668 | 舊 name／available／backend／effect／model_visible 欄位型別不變；新資料不得洩漏 credential 或 host 私密配置。 |
| `IntegratedCompanion._model_tools` | `respond`:462、`continue_after_tool`:697 | 首輪與工具後續輪都受影響；仍透過 Core／ConversationEngine／ModelRequest 傳遞原 ToolDefinition。 |

既有 MCP 的 `ToolCatalog.require` inbound trace 支持 `propose`／`execute` 兩個直接 caller，以及 hop 2 的 `_propose_tool_calls`。直接 source 額外證明巢狀 `execute.invoke` 的最後重驗，不能因 graph 未列出就刪除。`execute` outbound trace亦連到 catalog validation；`respond` outbound trace包含 `_model_tools`。其餘目標的專屬 inbound query 本輪 **NOT_RUN**，由直接 source 補足。

Graph 是靜態推論，`respond` trace 已截斷，不能當成完整 runtime impact 或執行證據。修復應只擴既有 ToolDescriptor／ToolCatalog 的唯讀描述；保留 proposal、argument binding、availability、取消、journal 與 executor 路徑。

驗收建議涵蓋既有 tool catalog／orchestrator、integrated companion、agent batches、context budget、execution lifecycle、gateway 和 model adapter suites；新增 discovery 的 executor spy、輸出副本不可污染 canonical schema，以及 unavailable／撤銷／legacy 相容負例。本子任務沒有執行這些 tests，最終結果由 root 記錄。
