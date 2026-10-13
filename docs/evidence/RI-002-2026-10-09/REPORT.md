# RI-002 — 唯讀能力說明與盤點交付

開始：2026-10-09；交付完成：2026-10-10，Asia/Taipei。證據目錄保留開始日期。**DONE：限定candidate能力inventory與本機整合驗收；不是自主技能、模型理解品質或正式產品發布。** 原RT/T/FIX編號、授權模式與聲線保留。

## 結果與產品入口

既有「電腦協助」新增「我現在能做什麼」：顯示能力中文名稱、可用／缺瀏覽器／工作目錄未就緒／使用者停用／未知原因，按「更新能力狀態」只讀狀態，不執行工具。資料沿原authenticated `GET /v1/runtime` 的 `tools`，沒有新endpoint／registry／executor／worker。

candidate模型每輪用同次capture取得可用ToolDefinition與工具metadata。首輪／工具續輪在既有journal checkpoint前更新first system message末端唯一SIRO-owned能力block；不改原生user/assistant/tool配對、call-ID、memory、approval或dispatch。快照只表示當次readiness；availability／required_permissions不是grant，也不是已執行成功。

未宣告output_contract／timeout等為null，不虛構接口；computer.execute timeout_seconds=120表示操作可指定上限，預設仍30s、run deadline可縮短，cleanup另有限制。browser readiness只查既有可執行檔存在性；workspace readiness只查既有process/client，未以此宣稱導航或任意硬體成功。legacy保留舊model schema／prompt，UI對無新availability欄位明示「尚未提供即時狀態」。

**部署範圍**：原8026未重啟／未修改部署設定，新後端需下次啟動載入。本輪真HTTP/Chrome跑在隨機loopback port＋temporary synthetic資料，已清理。未向現有私人對話送驗收訊息。

## Source與相容性

| 修改檔 | 目的 |
|---|---|
| `src/siro/services/tools/orchestrator.py` | optional typed ToolMetadata／ToolAvailability；單次capture；safe closed reason；deepcopy；原bool/positional constructor、ToolDefinition names/schema與require三個重驗接點保留 |
| `src/siro/services/presentation/integrated.py` | 同一capture供首輪／續輪tools與owned capability context；不累積messages；legacy保留；沿on_messages_ready checkpoint而非新Core路由 |
| `src/siro/services/presentation/gateway.py` | 現有builtin descriptor宣告中文labels／permission需求／來源／已知期限，readiness使用safe reason；不外送raw exception/env／private workspace root，不改批准風險分類 |
| `src/siro/services/presentation/static/index.html` | 同一runtime API的自然語言能力面板／唯讀刷新；textContent，error不洩canary／不保留失效可用狀態 |
| `tests/integration/test_capability_inventory.py` | 11項單capture、未知／exception、深拷貝、legacy positional、撤銷／metadata不授權負面驗收 |
| `tests/integration/test_capability_product.py` | 4項main/readiness/auth/privacy、initial/continuation/native pairing/legacy、新run刷新、真Node前端刷新與HTML injection驗收 |

先更新 [D36](../../DECISIONS.md)／[CONTRACTS](../../CONTRACTS.md)，再實作。同步STATUS、RI-002原卡與current audit/capability/design增補；保留RI-001及原盤點歷史。uv.lock／Cargo.lock／pyproject依賴不變，無schema migration；Core、permissions/grants、Skill/patch/release、Qwen worker/TTS/model adapters未修改。

## 證據與實跑

[baseline.json](baseline.json)記HEAD c1d2d41加本卡前dirty tree與256份source/test/script/lock SHA。此前RI-001的701PASS是先前完整結果，不冒稱本卡另跑了一次修前全套。[mcp-impact](mcp-impact.md)：本輪既有owner持開發MCP lease，啟動exit2；沒有關owner/繞鎖/重索引，重用同source SHA的RI-001 graph與本輪source/AST核對，不宣稱新MCP query成功。

[capture-before-after.json](capture-before-after.json)／[capture_probe.py](capture_probe.py)：trusted synthetic alternating-readiness在修前snapshot=True、隨後definitions=[]、兩次predicate；修後同capture=True、definition存在、一次predicate；兩版executor皆0。修前從本卡before讀入可信repo source，不使用HEAD回退或私人資料。

| 實際命令／驗收 | 結果／邊界 |
|---|---|
| `.venv/bin/pytest -q tests/integration/test_capability_inventory.py tests/integration/test_capability_product.py` | [specialized.log](specialized.log)：15PASS／3既有warnings，1.03s；包含於716，不重複加總 |
| `.venv/bin/pytest -q tests/integration/test_tool_catalog.py tests/integration/test_tool_orchestrator.py tests/integration/test_frontend_companion.py` | [first-adjacent.log](first-adjacent.log)：26PASS／3warnings，1.65s；同樣與全套重疊 |
| `.venv/bin/pytest -q -m 'not real_provider'` | [full-suite.log](full-suite.log)：716PASS／5 real_provider未選／3既有warnings，98.91s；不把耗時差當產品效能收益 |
| `.venv/bin/ruff format --check .`／`.venv/bin/ruff check .` | [format](format.log)271 files、[lint](lint.log)PASS；不格式化歷史source snapshots |
| `.venv/bin/mypy` | [types.log](types.log)：206 source files，PASS |
| `.venv/bin/python scripts/export_schemas --check` | exit0；無schema漂移 |
| `.venv/bin/python docs/evidence/RI-002-2026-10-09/verify_ui.py` | [ui-verification.json](ui-verification.json)：真Chrome154.0.8037.92／HTTP，13checks PASS；更新／停用恢復／401／惡意HTML literal，executor0、pageerror0、四production SHA起訖一致、完整cleanup；readiness/provider合成，不是LLM語意或Live2D/GPU驗收 |
| 暫存checkout `git apply --reverse --check`→reverse→reapply | [rollback.json](rollback.json)：4production＋2new tests精確還原本卡前dirty source與重套SHA，PASS；正式工作區未回退 |
| 原256份SHA＋8026 HTTP readiness | [preservation.json](preservation.json)：只4個允許production檔變；其他source/tests/scripts/locks不變，health/root/live2d HTTP200；readiness不等於真人對話/畫面完成 |

[capability-panel.png](capability-panel.png)是合成狀態的實際Chrome截圖；包含刻意惡意HTML literal卡，用來證明不當HTML執行，並非產品內建能力。所有命令在SiroV2 root，沒有讀私人DB／reference WAV／keys、GPU生成／cloud call或正式服務重啟。

初次新Model fixture漏`LanguageModel.name`，candidate專項1FAIL／14PASS；[initial-fixture-failure.log](initial-fixture-failure.log)保留，僅補fixture必需欄位後重跑，未降低production驗收門檻。初次Ruff raw JS行長／import順序已修正，最後format/lint/types皆PASS。

## 回退方法

[repair.patch](repair.patch)只含本卡4個production增量與2個新tests，以`before/`本卡開始快照為基準，**不是HEAD，也不會抹掉原voice/session修復**。維護時先drain owned work；核對相關檔未有後續改動，再對本卡patch做reverse check及reverse；保留privateDB與原runtime資料。若後續改動令patch不匹配，先review相衝突hunks，不git reset或直接整檔覆寫。

rollback.json已在TemporaryDirectory演練反向／重套與精確SHA；未做真正部署回退或接觸使用者資料。docs可移除本卡D36／RI-002契約與latest增補、restore原task狀態，保留歷史證據。

## 限制、freeze與下一卡

本卡只解catalog能力描述／可用性自我說明的接線，unknown output等不硬填。ToolCatalog/模型context/UI維持YELLOW；資料schema/identity/grants、generatedskill、untrustedchecks、autodeploy維持RED。沒有藉snapshot給Agent新權限。

未驗真provider能力回答品質、聲音、人眼Live2D/全身動作、硬體、24h／多owner／遠端CI；原FIX-005語音速度／人工语意、FIX-006理解仍未完成。FIX-007–009以及OS隔離／真正activation／保留最新資料回退仍阻擋對應自主接入。依一次一張卡規則，本輪只交付RI-002；下一張FIX-002應先重現search ScopeViolation、補safe原因，再驗公開查詢，不放寬scope掩蓋問題。
