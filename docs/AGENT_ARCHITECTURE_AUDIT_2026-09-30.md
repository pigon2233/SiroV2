# SIRO 智能體架構稽核

> **歷史快照（2026-10-24 標註）**：2026-09-30 的稽核快照。後續設計與實作見 `runtime-evolution/`（RT-001–015），現況見 `STATUS.md` 頂部「狀態總覽」。

日期：2026-09-30

## 結論

SIRO 目前是「已有許多智能體元件的對話應用」，還不是一個由持續內在狀態驅動的完整智能體。
問題不是只差一個更好的 prompt 或模型，而是產品執行路徑繞過了大部分已實作的認知元件。

目前真正運作的主路徑是：

```text
user text
  -> keyword/heuristic appraisal
  -> affect numbers and relationship numbers
  -> one assembled prompt
  -> LLM text or tool call
  -> tool execution
  -> tool observation inserted as another user prompt
  -> final LLM text
```

規劃文件所描述的 attention、workspace、persistent goal、action candidates、coping、proactivity、self-preference
development 和 consolidation 沒有在這條產品主路徑中共同決策。這就是元件測試大量通過，但親自使用仍不像
OpenClaw、Hermes 或具持續人格角色的主要原因。

## P0 結構性缺口

### 1. 缺少單一、持續的 Agent Runtime

`IntegratedCompanion` 同時處理事件、情緒、關係、prompt、工具提案、語音和身體。它不是可持續、
可恢復的 agent run state machine。無法一致地表示「我正在完成哪個目標」、「為什麼做這一步」、
「下一步依賴什麼」、「重啟後從哪裡恢復」。

需要新的 `AgentRuntime` 作為唯一產品入口，擁有 run/goal/step/observation/budget/cancel 狀態，
Conversation、Affect、Memory、Planner、Policy、Tools 都是它使用的服務，不再各自成為旁路。

### 2. 已實作的 Cognition 沒有進入真實對話與工具回路

`AffectDecisionLoop`、`Planner`、`SQLiteGoalRepository` 和 `GoalService` 主要出現在測試，沒有被
Gateway 的一般使用者 turn 呼叫。目前的工具選擇是 LLM 直接從 prompt 產生，不是先有 goal、
candidate actions、expected outcome 和結果比對。

須將每個使用者請求先轉為 `Goal` 或純對話 intent，再由 attention 選擇當前焦點，planner 產生
candidate actions，policy 做 hard gate，executor 產生 observation，verifier 決定 complete/replan/fail。

### 3. 模型邊界沒有保留原生對話與工具語意

Provider 每次收到一個巨大的 user prompt。工具結果也被重新包裝成 user text，而不是標準的
assistant tool-call + tool-result message pair。這會丟失誰做了什麼、使模型反覆讀取完整人設文字，並
容易產生報告式、英文或重複回答。

`ModelRequest` 需改為型別化 messages：system identity、developer policy、user、assistant、tool。工具 call id
必須在後續回合保留，並支援壓縮後的持續對話狀態。

### 4. 沒有將「想做什麼」與「怎麼說」分開

現在同一次 generation 同時做事實回答、角色扮演、情緒表達、工具規劃和最終措辭。
情緒數值雖存在，但沒有先形成一個可檢查的 `ResponseIntent`，例如回答、關心、澄清、
半開玩笑、拒絕、先行動、修復關係或安靜陪伴。

應新增「決策層→表達層」邊界。決策層輸出 intent、stance、disclosure、desired effect、
action/answer choice；表達層才把它同時映射為文字、TTS prosody、Live2D 表情與動作。

### 5. 工具不是持續的「觀察→操作→再觀察」環境

Browser driver 每次 navigate 都建立新 session 並關閉；`computer.execute` 是通用 argv，但沒有螢幕、
視窗、焦點、accessibility tree、持續 terminal 或 desktop state。因此它可以啟動程式，卻不能像
OpenClaw/Hermes 持續看到現在在哪裡、上一步改了什麼。

需要 session-scoped `ComputerEnvironment`，提供 observe/screenshot/accessibility/window/browser/terminal/file
等 semantic tools，每個 mutation 後自動 readback，畫面改變後使舊 target 失效。

## P1 人格、情緒與關係缺口

### 6. Affect 現在主要是觀測與表情資料，不是行為的真正因果

產品路徑會把 affect 數值寫入 prompt，卻沒有使用 `AffectDecisionLoop` 選擇實際行動。模型可以完全
忽略它，也可以用過度戲劇化的方式重新扮演一套情緒。

情緒必須先改變 attention threshold、goal priority、risk tolerance 的有界部分、coping candidate、
memory encoding 和 response intent，然後表達層只呈現結果。

### 7. SIRO 自己的偏好幾乎是種子資料，沒有經驗形成回路

`develop_self_preference` 要求多次來源才 committed，但真實工具成功、挑戰、挫折、互動後沒有
統一生成 preference evidence。目前整合層主要建立 owner 明示偏好，SIRO 的初始偏好則是啟動時寫入。

需要從已驗證 outcome 中產生候選偏好，在不同時間、任務和情境累積獨立證據；冲突、飽和、
衰減、修正與「還不確定」都必須影響後續選擇。

### 8. Relationship 數值有記錄，卻尚未形成關係行為

信任、熟悉、依附與 rupture 會更新，但還沒有系統性地改變稱呼、主動程度、自我揭露、玩笑尺度、
修復所需證據或對模糊請求的信任。「女兒」因此還是 identity 文字，不是長期互動後可觀察的
relationship policy。

### 9. Working memory 在程序記憶體，對話記錄雖寫入 SQLite 卻沒有在重啟後重建

重啟後 identity 和長期 memory 還在，但當下對話的未完成意圖、借代、語氣與前幾句細節不會從
`messages` 重建回 `WorkingMemory`。長任務、中斷回來、「繼續剛才的」容易像新會話。

## P1 對話體驗缺口

### 10. 沒有 Dialogue Policy 和對話行為評測

目前只驗收 streaming、cancel、記憶來源與最後一輪 1–5 分主觀體驗，沒有可重播的對話
eval set 檢查：是否過度列表、過度解釋、重複自我介紹、誤用敬語、回答不承接上一句、
在需要行動時只給教學，或在情緒時把內部數值說出來。

需建立三組固定評測：companion dialogue、agent task completion、relationship continuity。每組包含成功、
模糊、中斷、錯誤、不知道、衝突偏好和修復情境，以狀態轉移和使用者可見行為驗收，不以
特定文字比對作為主要分數。

### 11. 缺少會話層的節奏、立場和不行動能力

好的陪伴智能體不是每句都解決問題。當前系統缺少 backchannel、状態承接、保留懸念、不完整句、
適度沉默、主動提起舊事、自然改變話題與符合關係的不同意。只調 TTS 音色無法彌補這一層。

### 12. 身體、語音和文字不是同一個表達 plan

Live2D expression 在模型輸出前就根據 user text/affect 選定，文字是 LLM 稍後獨立生成，TTS prosody
再使用另一組映射。三者可能互相衝突，例如文字在安慰，臉卻顯示之前的 anger。

需要一個最終 `ExpressionPlan`：speech acts、text constraints、emotion display、gesture、gaze、pause、rate、
pitch、energy 與可中斷句段，同一份 plan 供文字、TTS 和 body 使用。

## P2 工程與運行缺口

### 13. Agent run 不能在重啟後恢復

Tool proposal 會持久化，但原始 goal、plan、step counter、model conversation、active process 和 pending observation
沒有統一持久化。服務在工具完成後、模型續接前重啟時，無法可靠恢復。

### 14. Cancel 沒有貫穿全部代理回路

Conversation cancellation 存在，但 pending proposal、running subprocess、detached GUI process、browser session 和後續
continuation 沒有共用同一個 run cancellation token。`_active_sessions` 也在等待工具時被移除。

### 15. 多工具呼叫、並行和失敗語意還不完整

同一回合有多個 tool call 時，目前可能對每個結果分別啟動 continuation。失敗只保存 exception type，
缺少 retryable、permission、missing dependency、invalid arguments、unknown outcome、partial success 等結構化分類。

### 16. 「預設全授權」需要真正的 Authorization Profile，不應只是布林開關

使用者已明確要求預設授權操作，所以產品可提供 owner `full` profile。但 profile 仍應明確記錄
actor、capability class、secret access、network、filesystem、desktop、device、privileged/root、有效期與撤銷。
Tools kill switch 和 OS 級緊急停止必須繞過模型。

sudo 目前需互動驗證。不應將密碼傳給 LLM 或儲存在一般設定。需要獨立 privileged broker，
驗證來自 agent runtime 的不可篡改 action grant，用完整 argv 執行，並保留 root-side audit/readback。

### 17. 沒有針對「像一個好智能體」的持續評測門檻

現有 acceptance 很強調元件安全、故障和 SLO，但 agent 品質只在最後以三輪 15 分鐘與平均分數
驗收。這太晚，也無法阻止「每個元件都通過但整體很機器」。

每個 agent architecture 變更都應重播固定任務軌跡，量測 goal completion、unnecessary turns、false success、
recovery、context continuity、personality consistency、initiative appropriateness 與人類主觀自然度。

## 修正順序

### A0：建立基準，停止繼續堆元件

1. 收集 30 組真實失敗對話，包含目前感到「機器」的例子。
2. 建立 companion、computer-agent、relationship 三組 replay suite。
3. 記錄當前 Groq 模型基準，分開「模型限制」與「系統編排錯誤」。

### A1：取代當前的 prompt-only ConversationEngine

1. 新增型別化 message/tool result 協定。
2. 建立 persistent `AgentRun`/`AgentStep`/`Observation`。
3. 以 verifier 決定 complete/replan/wait/fail，不信任模型自己宣告完成。
4. 讓 cancel、budget、generation fence 作用於整個 run。

### A2：把已有認知元件接入同一回路

1. 所有 user/device/system/internal events 先進 attention。
2. 將請求轉成 goal 與 action candidates。
3. 讓 affect/coping/preferences/relationship 實際改變 candidate 與 response intent。
4. 執行 outcome 同時更新 goal、world、affect、preference evidence 和 memory。

### A3：建立持續電腦環境

1. 每個 agent run 保留 browser/terminal/desktop session。
2. 加入 observe、semantic target、screenshot/vision、window/focus 和 filesystem tools。
3. 每步自動 readback，畫面變化後使舊 target 失效。
4. 用下載、安裝、啟動、設定與失敗恢復的真實任務驗收。

### A4：建立關係化的對話與統一表達

1. 建立 `ResponseIntent` 和 `ExpressionPlan`。
2. 用同一 plan 控制文字、語音、表情、gesture 和 pause。
3. 用關係歷史而不是固定 prompt 決定親密、玩笑、主動、修復和不同意。
4. 讓偏好從驗證經驗形成，並可被查看、質疑、更正與衰減。

### A5：才開啟 root/full autonomy

1. 完成 authorization profiles 與 privileged broker。
2. 做 root-side argument binding、audit、timeout、process-group cancel 與 readback。
3. 以隔離 VM/測試主機完成安裝、升級、服務修復和回滾情境。
4. 完成後再將 owner `full` profile 擴張到 sudo，同時保留硬 kill switch。

## 新的產品完成定義

SIRO 只有在以下流程成為單一可追蹤回路後，才可稱為完整智能體：

```text
event
  -> attention
  -> goal / dialogue intent
  -> candidates
  -> affect + preference + relationship bias
  -> policy / authorization / resources
  -> action or response intent
  -> execution
  -> observation + verification
  -> world / goal / affect / memory / preference update
  -> unified expression
  -> next attention cycle
```

這個回路必須可取消、可重啟恢復、可重播、有預算、有來源，並在同一組長期體驗評測中同時證明
任務能力、關係連續性與表達自然度。
