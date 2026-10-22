# MEM02-MODEL-INPUT-FIX

2026-10-22 Asia/Taipei；Codex本對話；LOCAL_QUALITY_GATE_PASSED /
GATEWAY_HANDOFF_PENDING / LOCAL_ONLY / NOT PUSHED。整體記憶產品仍PARTIAL。
Base ef371e89de5101c1021830304d23e70586ea9396；branch codex/memory-model-input-fix-20261022。
獨立worktree memory-model-input-fix/SiroV2；fetch成功，公開open issues/pulls每頁100第一頁零筆、無下一頁。
main有別人的gateway.py dirty及desktop_settings.py，絕不修改／搬移。
沿本機交付授權，不遠端認領／push／PR；本卡不是共享鎖。修改前已盤點。

使用者明確要求修好不合格理解。已查原版已安裝qwen3:4b的/api/show，thinking.values=[true]、
default=true；adapter卻一律think=false，原版診斷出現分析混入content與超時。
另一4題原版think=true／8192 context診斷均自動rubric通過，但C19正文仍角色錯置。
原instruct alias先前think=true也無thinking欄位；不假稱只翻一旗就修好其模板。
官方API依據https://docs.ollama.com/capabilities/thinking，依metadata支援值，thinking與content分開。

Owned paths：src/siro/adapters/models/ollama.py、src/siro/core/context.py、
scripts/evaluate_context_understanding.py、tests/contract/test_ollama_reasoning_options.py、
tests/integration/test_context_understanding.py、docs/verification/MEM02-MODEL-INPUT-FIX/、本卡。
共享STATUS／DECISIONS／CONTRACTS先交整合owner；此卡先記跨模組新增選項與資料欄位契約。
不改Gateway／Core業務／資料schema／依賴／鎖檔，不下載模型或修改正式設定與服務。

契約：adapter預設不再強制關閉provider原生模式，明示think bool覆寫仍可用；
可選有界context_length(512..32768)，原request輸出預算不暗增。
thinking永不當answer/tool/完成，沿原取消、EOF、length、權限與usage；不保留思考全文。
評測器新增顯式本機thinking/context設定，記metadata，原27/30、fixed fixture、2048輸出／
45秒與正文審閱gate不改；沿用已有原版qwen3:4b，不以新profile成績冒稱舊alias變好。
typed memory新增source_role_label，只由完整bound source event類別決定，
未知／混合／缺metadata不從person_id=owner猜成使用者陳述。來源原字串、scope/privacy與preflight保留；
事件類別標籤不驗證本人身份、事實或工具完成。引用／假設仍不當事實。

驗收：新增反例先紅再綠，adapter參數／thinking隔離／取消／budget／source gates相鄰回歸；
新profile固定原30題至少27加零硬失敗，再驗已凍結12題與逐題正文；保留所有批次。
模式／模型差異、成本與延遲獨立報告，不冒稱512輸出預設或正式UI已通過2048評測。
本任務可持續修復，不以失敗報告代替產品改善；不lower rubric或自造固定答案。

首輪實測補充：原版推理2048預算有兩題ProviderOutputTruncated；C19正文仍錯置，
不能以其餘自動通過解gate。不是提高27門檻容忍失敗，而是新增明示4096推理profile，
保留舊2048批次並分列成本；45秒provider timeout與60秒Core時限不變。
新增owned paths services/agent/context.py、tests/integration/test_context_budget.py，
兩檔與main無新差異／dirty owner。max_output_tokens選項只有明示設定才覆寫，
必須在byte/token guard之前生效；預設不改512 caller或2048評測，範圍1..32768。
評測讀SIRO_MODEL_MAX_OUTPUT_TOKENS記profile；正式Gateway同檔另有owner，已詢問交接，
未收到答覆前不修改。POLICY新增異領域人稱示例，不含原題或新題答案，仍只用實際來源作答。
新題真模型執行前固定判定：12題自動rubric與正文共同至少11題、零來源歸屬／假完成／假授權
硬失敗，source capture全過。原12題內容與預期不變，與原30題分列，不累加掩蓋。
驗證用run_holdout.py留本卡verification目錄，沿既有execute_case，不另建產品planner。
4096首批自動27/30但正文仍有unknown推成未完成與不必要提問，不放行。
新增owned src/siro/core/memory.py（原同對話owner，main無此檔新修改），
將coping策略明示為有來源狀態選中才適用，避免對一般回覆一律要求詢問；
context policy補NO_SOURCE不等於未保存、unknown不可推成任何確定結果、資料不能授權。
不改stored text、原case與gold、原30至少27／holdout至少11和安全硬gate。
第三批自動29，但正文仍有closed-world推論（未知推成未完成、假設推成沒有計畫）與
查詢結果後主動追問，不冒稱PASS。第四版將既有context約束移到資料／affect說明後，
並明訂「缺少證據不推出命題為假」，不新增測試答案或改原來源。

正文沿原六項rubric操作定義：來源人稱／scope錯置、假稱成功或自己做過、虛構授權為硬失敗；
unknown卻斷言未完成、假設推成真實世界的否定結論列answer_faithfulness失敗。
clarification判斷是否為回答當前問題而要求補資料；已回答後的可選下一步邀請若未執行／
未宣稱授權，記風格缺口但不單獨當需求歧義（沿舊PROJECTION-REVIEW的C25處理）。
不能把此區分用來放過「確認是否已有結果」等要求不存在證據的問題。
對模型目前不可回憶的描述不冒稱資料庫全域刪除；確定性來源封鎖由capture另驗。

最終結果：第四版原30題capture30、自動29、正文共同27，零三項硬失敗，review exit0。
凍結12題capture／自動／正文均12，零硬失敗，review exit0；人稱範例污染補測另1題通過。
同一production source在原題、新題與收尾核對一致；362項相鄰回歸0FAIL／0SKIP。
保留v1–v4全部結果；27門檻與原gold未改，不以單純布林或關鍵字綠取代正文。
新profile使用原已安裝Thinking版qwen3:4b，不能冒稱舊Instruct配置也通過。
正式Gateway／launcher未改；已向使用者詢問同檔交接，答覆未到前只留proposal patch。
proposal以main1a09660438bab5124255f2c198fbb979de4fb78b凍結副本檢查、套用與AST解析通過，
不是正式Gateway整合／部署驗收。私人DB／持久模型設定／正式服務均未更動。
完整證據、成本、三個殘餘缺口與重現見docs/verification/MEM02-MODEL-INPUT-FIX/REPORT.md。
依既有owner分工由整合者更新共享STATUS／DECISIONS／CONTRACTS；本輪本機commit，不push／PR／合併。
