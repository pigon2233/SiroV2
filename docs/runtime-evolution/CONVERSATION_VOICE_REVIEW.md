# 對話與語音產品檢視、最小修復規劃

最新實作進度（2026-10-07）：使用者授權施工後，**FIX-003、FIX-004 DONE / VERIFIED**；[003真配置模型證據](../evidence/FIX-003-2026-10-07/REPORT.md)、[004固定源碼真UI跨TTL與554項整體回歸](../evidence/FIX-004-2026-10-07/REPORT.md)。FIX-005／006尚未完成；原始樣本截斷根因仍未知。未部署私人服務，下方現象與靜態檢視保留規劃時點。

原始 review 日期：2026-10-07（Asia/Taipei）；基準 c1d2d41。下文為修前檢視／規劃快照，當時未修改 production 或執行功能驗收。

使用者補充的三件事合併進產品方向：自由活動桌寵與動作製作、近期對話理解品質、語音生成等待與長文講不完。桌寵詳見 [COMPANION_EVOLUTION_PLAN](COMPANION_EVOLUTION_PLAN.md)；本文件聚焦後兩者，搜尋 FIX-002 仍保留。

## 檢視範圍與證據界限

依使用者「檢查最近的對話紀錄」授權，以 SQLite 唯讀連線、query_only 檢查本機既有資料。樣本為當日 15:40–16:07 的 14 個最近 run：10 completed、4 failed；失敗 error 類別為 3 HTTPStatusError、1 ValueError。這是有界樣本，不能推論長期故障率。另檢查近期服務紀錄中的狀態碼，以及 8 個語音快取的 WAV headers；未播放音檔或重新生成。

只把**當前 user goal 之後的新 assistant 訊息**視為當輪回覆；failed journal 內攜帶的舊對話不算新回覆。這 4 個 failed run 沒有新的非空 final，不能說它們重複回答了舊內容。未重播私人對話／工具、呼叫 provider、匯出 DB、存 raw transcript／log／音檔到 evidence；本文件使用匿名現象與合成驗收案例。秘密設定未讀取。

## 實際發現與分類

| Finding | 分類／來源 | 已確認的 evidence | 尚不能確定 | 處置 |
|---|---|---|---|---|
| CV-01 句中截斷被當完成 | REQUIRED_FIX；IMPLEMENTATION_BUG、BAD_INTERFACE、TEST_GAP | 至少 3 個 completed final 在句中停止，持久文字本身已不完整；adapter 忽略 finish_reason，非空 SSE EOF 仍 finished，Core 預設 completed | 這些實際 run 是 token limit、傳輸中斷或模型輸出造成，因未留終止原因無法辨別 | FIX-003：先恢復完成／未完成的正確裁決，再調有界輸出 |
| CV-02 頁面連線憑證不續期 | REQUIRED_FIX；MISSING_INTEGRATION、IMPLEMENTATION_BUG、TEST_GAP | SessionTokens TTL 300 秒、session API 回傳 expires_in_seconds；頁面只在 boot 取一次 token。受檢服務紀錄有 4 筆 turns POST 401 | 不能把所有 run 的 HTTPStatusError 都當成這些 gateway 401；provider 上游失敗另查 | FIX-004：小範圍續期與拒絕後恢復，不延長為永久憑證 |
| CV-03 語音整段等待、長文無完成保證 | REQUIRED_FIX；MISSING_INTEGRATION、BAD_INTERFACE、TEST_GAP | UI 等 assistant_terminal，再等整個 speech response.blob 才播；worker 整段生成，codec max_new_tokens=512；未檢查尾端完整性便快取 | 當前冷／暖生成時間、硬體瓶頸、實際語句尾端缺失原因尚需新合成實測 | FIX-005：有界分句、順序播放、生成完成證據與取消 |
| CV-04 不理解自己剛發生的故障、回覆空泛 | REQUIRED_FIX；MISSING_INTEGRATION、TEST_GAP；模型行為歸因待查 | 對自身 UI 故障的追問被回答成另一個 API 的一般教學；口語更正後仍要求轉用外部 TTS。下一輪只恢復 completed 對話，沒有失敗 run 的安全診斷摘要 | 語氣／理解落差各有多少來自模型、prompt、截斷、缺上下文：UNKNOWN — NEEDS INVESTIGATION | FIX-006：先驗證並補最小 own-runtime facts；用合成多輪評估，不先換模型或重做記憶 |
| CV-05 缺少近期端到端效能與聽完證據 | TECH_DEBT；TEST_GAP | 舊 GPU cold render 與 cache hit 證據不能證明目前 first-audio、長文尾端與連續使用品質 | 現行 p50／p95、暖生成 RTF 與播放間隙未知 | 必要量測併入 FIX-005 驗收；不另造通用 profiling framework |

已完成的 greeting、記憶能力說明與真 provider 接線保留。樣本含正常招呼、唯讀電腦操作後自然整理與完整短故事，不支持「所有對話都走假模型／沒有記憶」的結論；也不代表上述缺陷不存在。不將整批既有 RT 改為 FAILED_VERIFICATION。

## 文字完整性與自身情境

證據路徑：[ModelRequest](../../src/siro/ports/models.py) 的預設 max_output_tokens=512；[ConversationEngine](../../src/siro/core/conversation.py) 建立 request 未覆寫此值；[OpenAI-compatible adapter](../../src/siro/adapters/models/openai_compatible.py) 送 max_tokens、忽略 finish_reason。這個 **512 是文字 token 預算**，與下文語音 codec 的 512 是不同限制。

先使 length、非正常結束與 transport 中斷不能假裝完成；保留 partial 與一次 terminal，failed intent 不 dispatch。實際截斷根因仍需合成重現，不能靠標點猜完成，也不能只加大上限或自動重送含工具的 run。若需要調整回覆長度，沿用 native context budget，預留有界 output，不繞過 RT-011。

[recent_session_messages](../../src/siro/services/agent/runs.py) 只恢復 completed user/final pairs，避免重播 intents 的設計仍有效；不要把 failed journal 全部塞回 prompt。[integrated runtime facts](../../src/siro/services/presentation/integrated.py) 已說明記憶、語音與 Live2D 能力，但缺少當前同 session 的故障狀態與已知／未知界線。先透過既有 composition 補固定、短小、同 privacy 的 operational facts，不能把完整日誌、憑證或工具輸出變成 system 指令。

合成多輪驗收需包含：

- 「聲音等很久」→「我想聽她說話，只是要快一點」：保留開聲需求，理解更正，給出當前可做的處置；不擅自關語音或要求使用者另找 TTS。
- UI 已有同 session 故障→「你剛才自己報錯，幫我看」：辨識是本產品，已知狀態與原因未知分開；能用已授權觀察就觀察，未觀察不能聲稱修好，不反覆索取 API key。
- 日常招呼／閒聊、口語代詞與連續更正：自然承接，不把每輪結尾固定寫成客服詢問；不捏造私有記憶、能力或已做的操作。
- 文字生成中斷、工具做完但 final 失敗、重啟與取消：既有成果可回讀，不重做真實效果，不能用舊 assistant 冒充新 final。

先比對修復前／後相同合成案例，再判斷模型或 prompt 是否仍限制品質；mock assertions 只能驗 wiring，真實理解要以同配置 provider 的合成多輪結果獨立記錄。模型替換需證據與成本／延遲比較，不是本輪預設方案。

## 語音：目前為何等、為何可能講不完

目前實際產品路徑：

`完整文字 terminal → UI 整段 POST /v1/audio/speech → Qwen 整段生成 WAV → 全部回傳 → blob 就緒 → 播放`。

- [UI](../../src/siro/services/presentation/static/index.html) 的 assistant_terminal／playTts、[Gateway](../../src/siro/services/presentation/gateway.py) 的 render_owned_speech 都等待完整產物。既有 [speech_segments](../../src/siro/services/audio/tts.py) 只在另一條 synthesize_or_fallback 路徑被使用，現行 Qwen render 沒有使用；不需要因此另造一套音訊框架。
- [worker](../../scripts/qwen_tts_worker.py) non_streaming_mode=True、max_new_tokens=512，整段 WAV 成功回傳就按 text hash 快取。**這是音訊 codec token 上限，不是可朗讀的中文字數**。目前沒有 EOS／達上限的回報，HTTP 200 也不等於講完。
- 受檢最近 8 個 WAV header 中，當日有兩個都長 40.88 秒，另有 29.60 秒；相同長度與固定生成上限一致，但未聽音或對齊尾端，**不能單憑時長確認截斷根因**。合成長文需驗最後一句與產生終止原因。
- SpeechInput 每次最多 4,000 字；超過會遭 schema 拒絕，不是自動朗讀下一段。近期樣本未證明觸發此限制。
- 格式化 UI 回傳 DOM textContent，code fence 已消失但 code 內容仍在，可能繞過後端 code-block 排除。朗讀來源應取保留語義的 canonical 文字，不能以畫面重排後文字做唯一依據。
- RT-006 [歷史實測](../evidence/RT-006/README.md) cold load＋首 render 25.700 秒、同文 cache hit 0.00218 秒；只是舊單次樣本，不是現行速度或 p95。當前 load／queue／warm render 分項時間尚未量到。

Qwen 官方介面說明 non_streaming_mode=False 只模擬 streaming text input，這個 generate API 不因此變成真正的逐音塊回傳；不可只翻旗標就宣告串流完成。[官方 inference 介面](https://github.com/QwenLM/Qwen3-TTS/blob/main/qwen_tts/inference/qwen3_tts_model.py)

## 最小語音交付切片

1. **先讓長文完整、能早播第一段**：重用 segmenter，按句／語義邊界切有界片段；每段生成完成便順序播放，播放時最多預取下一段。仍只用一個 owned worker，不平行開多份模型。每段都小於 API 長度上限；初始字數用合成中文／英數混合實測決定，不能將「180 字」當成必然講得完。
2. **再縮短等待文字的時間**：第一切片仍等 final text，需誠實記錄；後續只在 final-answer channel 已提交完整句子後提早排入語音。tool planning／中途草稿不得朗讀，改寫／失敗／新 turn 受 generation fence；現契約無法區分時先維持 final 後分段，不擴張 Core 來追求假串流。
3. **語音表達與全文分開但透明**：一般聊天短句、少表格／長 checklist；需要細節時畫面可展開。若提供精簡朗讀，明示是摘要並保留完整朗讀入口；使用者要求故事或全文，必須逐段講到底，除非取消或明確故障，不能默默省略後半段。
4. **完成證據與失敗恢復**：回報 segment index／總段數／終止類型；達 codec 上限或無法確認完成，不快取為成功。以生成設定、voice／model 與分段版本隔離快取，既有可能截斷的音檔不能直接當新版通過。失敗保留已播進度並明示，禁止自動從頭重播整輪。
5. **保留生命週期**：沿用 request_id／epoch、max_pending、cancel／close／reap；使用者輸入、停止／關聲、離線或 owner 交接，立即停播並取消待播／預取，舊音檔晚到不能復活；不把情緒或嘴型重設成另一個人格。

第一切片使用現有 voice/reference，不為降低延遲偷偷換成 OS 聲音。若暖生成實測仍慢，再以實際硬體評估推論設定、受控預熱或可回退 backend；不在本輪啟動 GPU、不先換聲線。上游宣傳延遲不能當 SIRO 實測。

## 驗收量測與發佈 gate

| 類型 | 必須驗到的產品結果 |
|---|---|
| 速度 | 分開量 text first delta／first committed sentence、queue wait、model load、first segment ready、first audible；cold／warm 各以非快取合成文字量測，報 p50／p95、RTF 與播放間隙。cache hit 單列，不能混算暖生成 |
| 完整性 | 短句、長中文、英數混合、長於現有約 40 秒樣本、超過單次 4,000 字的合成文件：先逐段比對輸入完整覆蓋，再驗首尾句實際朗讀；拼接 WAV 或 HTTP 200 不是聽完驗收 |
| 可打斷 | 首段生成／播放／下一段預取時取消，新 turn、重連及 owner 切換；沒有漏播、重複、交錯、晚到復活，worker 可收尾重用 |
| 對話 | 上述合成更正／自身故障／自然閒聊案例；保留 native budget、privacy、真工具結果與失敗狀態，不以假的聰明回覆蓋過錯誤 |
| 連續使用 | 超過 300 秒、分頁掛起喚醒、Gateway 重啟與 token 過期：仍可文字／語音互動，無未授權繞過或副作用重送 |

發布前需依目標硬體寫下實際 latency 門檻並由實測驗收；本輪沒有數據可承諾幾秒。明確可先驗的改進是：不必等全篇音檔生成才聽到第一段、全文內容受覆蓋檢查、未完成有清楚狀態、停止不復活。

FIX-003／004／005／006 的完整範圍、測試、rollback 與風險見 [FIX_REGISTER](FIX_REGISTER.md)。各 gate 僅限制相關產品 promotion：不把它們擴張成桌面素材、場景原型或本機唯讀整理的全面 blocker。原 RT 編號與已完成切片保留；本輪沒有新增 architecture correction，沒有證據要求重設計整套 SIRO。
