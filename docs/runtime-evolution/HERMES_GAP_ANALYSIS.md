# Hermes gap analysis

## 2026-10-13 — RI-005 D52 signed source launch / readiness VERIFIED

**REJECT** 第二updater/owner/registry/schemaengine、global state abstraction。原ReleaseManager+launcher/Gateway已提供此sourceidentity價值，不為概念完整擴框架。

**KEEP** 實際caller、來源identity、取消/ownership與可回退驗收；**DEFER** arbitraryselfmodify/autopublish、新deps/ABI/跨平台untilconcretecaller與批准/隔離/handoff證据。RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：舊／非受管writer停止、parent驗簽後sameUID換包、maintenance→exec CLOEXEC空窗與人工批准handoff未解除。D52只證同schema／D52-compatible src package，任意deps/ABI/migration/其他OS/powerloss/正式deployment未證。FIX-002/005/006產品gates、RT-011/013/015原scopedDONE不變。

[實際驗收、限制與回退](../evidence/RI-005-launcher-2026-10-13/REPORT.md)。

## 2026-10-13 — D51 / FIX-015 backup cancellation VERIFIED

**REJECT** 為backup cancellation再造manager、executor service、第二owner registry或全域state abstraction。實測已由原SQLiteStore／CLI composition局部修復，不為完成Hermes概念清單繼續擴張。

**KEEP** 來源、bounded ownership、失敗可見與驗收導向原則；**DEFER** 任意code generation／自動發布／cross-platform和multiprocess profiles到具體caller、實際收益與各自安全gate成立。RI-005整體仍 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**：first-adoption舊／非受管writer停止、真正signed launcher/version/readiness與人工批准handoff仍待各自驗收。FIX-002有用搜尋、FIX-005語音速度／人耳、FIX-006理解產品gate保持；RT-011/013/015原scopedDONE及編號不改。

[驗收、分類、限制與回退](../evidence/FIX-015-2026-10-13/REPORT.md)。

只參考官方 NousResearch/hermes-agent，鎖定 commit `f42f579cf8bac4918ac9599bece71618afadd846`（2026-09-30 取得）。閱讀 source，不執行 Hermes，也不新增依賴。下列是設計比較，不保證 Hermes 在 SIRO 環境可用；本次未跑 Hermes tests。Provider/Memory 的深入子模組覆蓋有限，保持比較範圍。

| Hermes concept | SIRO equivalent | Current status | Gap / actual problem | Concept class | Recommendation | Priority / risk | Primary source |
|---|---|---|---|---|---|---|---|
| Agent Loop | IntegratedCompanion/ConversationEngine | PARTIAL | batch continuation/lifecycle；F01/F02 | ADAPT | EXTEND | HIGH；message protocol regression | [agent/conversation_loop.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/agent/conversation_loop.py) |
| Tool Registry | ToolOrchestrator executor dict / SkillRegistry | PARTIAL | schema/handler 多份來源；catalog 不一致 | ADAPT | WRAP | MEDIUM；availability 相容 | [tools/registry.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/tools/registry.py) |
| Provider abstraction | LanguageModel / adapters | PARTIAL | 已有 stream boundary；不需另換 framework | ALREADY_EXISTS | KEEP | LOW；保留 ports | [run_agent.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/run_agent.py) |
| Provider routing | Router + main env selection | PARTIAL | router 未接主入口；配置/成本未共用 | ADAPT | EXTEND | MEDIUM；外送/費用 | [run_agent.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/run_agent.py) |
| Session | SQLite conversation + WorkingMemory | PARTIAL | resume 未還原 context；F04/F08 | ADAPT | EXTEND | HIGH；歷史資料相容 | [hermes_state.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/hermes_state.py) |
| Memory | MemoryService/source revisions | PARTIAL | chat ingress 未驗；F08；Hermes memory 不應替代 SIRO 人格記憶 | FUTURE | KEEP | MEDIUM；過度吸收個資 | [hermes_state.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/hermes_state.py) |
| Context compression | bounded deque | MISSING | 沒有 token-aware compression；長 context/goal 遺失 | ADAPT | ADD | MEDIUM；摘要丟失來源 | [agent/context_compressor.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/agent/context_compressor.py) |
| Retry | 部分 job policy | PARTIAL | main provider retry 未明定；暫態錯誤處理 | ADAPT | WRAP | MEDIUM；重複副作用 | [agent/conversation_loop.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/agent/conversation_loop.py) |
| Fallback | FailoverModel | PARTIAL | main 未使用；F07 | ALREADY_EXISTS | EXTEND | MEDIUM；tool emission 後重試 | [run_agent.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/run_agent.py) |
| Cancellation | CancellationToken | PARTIAL | 未到所有 executor；F03/F05 | ADAPT | EXTEND | HIGH；child ownership | [agent/tool_executor.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/agent/tool_executor.py) |
| Persistence | SQLiteStore + run/proposal repos | PARTIAL | recovery contract 缺；F04 | ALREADY_EXISTS | KEEP | HIGH；schema 不應隨意更換 | [hermes_state.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/hermes_state.py) |
| Tool availability | static catalog | PARTIAL | 無 readiness predicate；無效工具仍提供 | ADOPT | WRAP | MEDIUM；snapshot stale | [tools/registry.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/tools/registry.py) |
| Error wrapping | exception type only | PARTIAL | 不可辨識 retryability/outcome；工具不能據此可靠補救 | ADAPT | EXTEND | MEDIUM；error secret redaction | [tools/registry.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/tools/registry.py) |
| Execution backend abstraction | Runtime port + direct closures | PARTIAL | formal path bypass；F03/F06 | ADAPT | WRAP | HIGH；permission compatibility | [tools/terminal_tool.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/tools/terminal_tool.py) |
| 整體 framework replacement | 現有 SIRO | PARTIAL | 無必要證據；不可破壞 identity/Live2D/device boundaries | REJECT | REJECT | LOW；大規模 regression | [run_agent.py](https://github.com/NousResearch/hermes-agent/blob/f42f579cf8bac4918ac9599bece71618afadd846/run_agent.py) |

Registry 的 register/check_fn/requires_env 與 dispatch/error normalization 提供可用性、註冊和回傳邊界參考。Conversation loop 包含 retry/interrupt/compression 的控制點；compressor 有 threshold、timeout/cooldown 與 fallback summary；terminal backend 保留 session cwd/process lifecycle。這些觀察只支持選取小型邊界，不支持移植整個 runtime。上述每列 link 對應本次讀取的固定版本。
