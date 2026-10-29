# CONSOLE-REDESIGN-PLAN：控制台重造、記憶自我整理、主線／子線對話

Owner：Claude（thread「siro 製作」）；2026-10-29；狀態：PLAN COMPLETE, AWAITING OWNER REVIEW / LOCAL_ONLY / NOT PUSHED。
Base：`8d60f833f8742eabc9f3782425b3331e28f3c8f1`（local main）。
範圍認領：協調者已確認無其他任務持有記憶與對話多執行緒；TTS streaming（f52018d）、
claude.ask 更名、ESP32 韌體屬其他範圍，不碰。本檔只是計畫，**尚未改任何產品程式**。

## 0. 使用者要求（原話摘要）

1. 控制台整個重造；任務／記憶／設定頁「缺乏必要、價值、實用性，正常使用不會打開」。
2. 藏起來不算解決；「有存在必要嗎」，參照 Hermes agent 沒有這些頁面。
3. ESP32 回傳值與 SIRO 在電腦上取得的值，另做一個監測器頁面。
4. 真正需要的是**多執行緒（子線）與主執行緒**：目前所有內容塞在同一個對話。
5. 記憶要**自己處理**：自己分析有效／無效、長期／短期，像真正的記憶。
6. 先把所有細節規劃清楚才動工；不臆測，有疑問上網查。

## 1. 實測現況（2026-10-29，執行中服務，唯讀查詢）

| 項目 | 實測 |
| --- | --- |
| ESP32 `siro-node-mqtt-01` | 只有 `illuminance`(20)、`motion`、`button_down`、`button_press_count`；**無溫度／濕度**。另有 HTTP 節點 `siro-node-01` 全為 unknown |
| 電腦端 SIRO 取得的值 | 只有 `/v1/work-context`（app 類別、螢幕亮度），預設全關、目前為空。**沒有 CPU／記憶體／磁碟** |
| 記憶品質 | 目前僅 9 筆，**全是 `kind=self`**，內容皆「我自己查過「…」，看過：…」，主題高度重複（同一「環境干擾」查了 4 次）。來源：`services/agent/self_notes.py:247` 每次自主研究都寫一筆，無去重、無過期 |
| 記憶資料模型 | `core/memory.py` 有 `MemoryKind`(working/episodic/semantic/procedural/self)、`valid_to`、`confidence`、revision。**沒有重要度、最後使用時間、層級（短／長期）欄位**；`WORKING` 不寫入 DB |
| 自動記憶 | `integrated.py:806`：每輪回覆後背景呼叫 `AutonomousMemory.consider`（上限 3 筆、須原文引用、敏感詞須確認），`SIRO_AUTO_MEMORY=0` 可關 |
| 閒置整理 | `services/agent/organization.py` 只把 EPISODIC 分組成「可拋棄摘要」，**不寫入、不刪除、不升降級** |
| 對話 | `core/conversation.py` `ConversationEngine.respond` 以 `session_id` 為單位；`WorkingMemory` 每 session 最多 12 則。背景工作（self_notes、tool、goal-task）事件與使用者對話共用同一個顯示串 |
| UI | `static/index.html` 2699 行，8 個頁面（對話／任務／活動／記憶／能力／設定／權限／系統） |

## 2. 外部參考（已查，來源如下；二手部落格只作旁證）

- Hermes Agent 官方文件 Memory：<https://hermes-agent.nousresearch.com/docs/user-guide/features/memory>
  - MEMORY.md 約 2,200 字元、USER.md 約 1,375 字元，session 開始時凍結注入。
  - 額滿**不會**靜默丟棄，而是回錯誤，要求代理在一次 batch 內合併／刪除（建議 >80% 時合併）。
  - **沒有**時間衰減；修剪由代理自己做。歷史對話存 SQLite FTS5，按需搜尋，不進 prompt。
  - 無獨立的記憶／任務管理頁面：全靠對話與 CLI。這支持「頁面不必要」。
- Letta sleep-time compute：<https://www.letta.com/blog/sleep-time-compute>
  - 主代理負責即時對話，**不能**改核心記憶；另一個 sleep-time 代理在背景整理並改寫共享記憶區塊。
  - 觸發頻率可設定；頻率越高越耗 token。對應本需求「主線／子線」＋「記憶自己整理」。
- Hermes 官方文件 Delegation：<https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation>
  - 子代理「全新對話、獨立工作」，只拿父代理給的 goal／context；**只有最終摘要進入父代理 context**。
  - 預設同時 10 個子代理、每個上限 250 個工具回合；預設不可再委派（`max_spawn_depth`=1）。
  - 450 秒無進展（工具內 1200 秒）判定卡住並中斷；停止後回 `status="interrupted"` 含部分結果。
  - 使用者看得到：CLI 樹狀即時進度、桌面版在輸入框上方預覽最多 3 個 worker。
- Generative Agents（Park 等，2023）全文 <https://ar5iv.labs.arxiv.org/html/2304.03442> §4.1：
  檢索分數＝recency＋importance＋relevance（各自 min-max 正規化到 [0,1]，權重皆 1）；
  recency 以「距上次被檢索的遊戲小時」做指數衰減，係數 0.995；importance 由 LLM 在建立時
  給 1–10 整數分；relevance 為 embedding 餘弦相似度；近期事件 importance 總和超過 150 觸發反思。
  注意：這是**檢索排序**，論文本身不刪除記憶。
- Mem0（Chhikara 等，2025）<https://arxiv.org/html/2504.19413>：每個候選事實先取向量最相近的
  10 筆既有記憶，再由 LLM 以 tool call 選 ADD／UPDATE／DELETE／NOOP 四種操作。
- SCM（睡眠整合＋刻意遺忘）arXiv 2604.20943 僅為近作旁證，未驗證，不作設計依據。
- psutil 7.2.2：BSD-3-Clause，支援 Windows／Linux（<https://pypi.org/project/psutil/7.2.2/>）；
  已透過 `amqtt` 鎖在 `uv.lock`，改為直接依賴不會新增套件。

結論：參考系統都不在時間到期時硬刪除（Hermes 無衰減、Generative Agents 衰減只影響排序）；
「自己整理」的共同做法是**寫入時比對相近記憶決定新增／合併／更新／不動**（Mem0），
加上**背景代理整理**（Letta）。這兩點是本設計的主軸，衰減只用在排序與降級，不直接刪資料。

### 2b. 其他長期使用型代理（2026-10-29 補查，使用者要求）

| 系統 | 查到的做法（來源） | SIRO 採用 | 不採用 |
| --- | --- | --- | --- |
| OpenClaw | `MEMORY.md` 精選長期＋`memory/YYYY-MM-DD.md` 每日筆記（只索引、不每輪注入）；session 開始載今天與昨天筆記；壓縮前跑**靜默 memory flush** 先存重點；**dreaming** 評分短期候選，需過 score、recall 次數、query 多樣性三道門才升級；**不可信與系統衍生候選不升級**；混合檢索（向量＋關鍵字）（<https://docs.openclaw.ai/concepts/memory>） | 升級三道門（D1）；網頁研究等不可信來源**只進檔案層、永不升核心**；長對話摘要前先 flush（接 RT-011 `summary.py`）；整理紀錄給人看（對應 DREAMS.md，放監控頁） | 以 Markdown 檔當真實來源（SIRO 已有 SQLite＋來源契約）；官方頁未給數值門檻，不自訂 |
| Zep／Graphiti | 雙時間軸：事實有效區間 `t_valid/t_invalid` 與系統建立／失效時間分開；新資訊矛盾時把舊事實的 `t_invalid` 設為新事實的 `t_valid`，**不刪除**；新資訊優先；去重用 embedding＋全文混合，再由 LLM 判定（<https://arxiv.org/html/2501.13956>） | 閘門的 DELETE 改為「設定舊記憶 `valid_to`＝新記憶 `valid_from`」並保留 revision；SIRO 已有 `valid_from/valid_to`，不需新表 | 知識圖譜與圖資料庫（新依賴、規模不需要） |
| ChatGPT | 兩套：明確「已儲存記憶」與會變動、只保留部分細節的「參考聊天紀錄」；官方建議要它一定記得的放已儲存記憶；**暫時聊天不使用也不建立記憶**；關閉記憶不刪除既有資料（<https://help.openai.com/en/articles/8590148-memory-faq>） | 使用者說「記住…」直接進核心層、不參與自動降級；新增「這段不要記」暫時模式（P2 一併做） | 雲端摘要式 memory summary（違反 local-only 底線） |
| Letta／Hermes | 見 §2 | 已採用 | — |

二手文章提到 OpenClaw 2026 年有大量壓縮相關 bug（fast.io 指南），未核實，只作提醒：flush 須有測試。

## 3. 目標設計

### 3.1 前端：兩個畫面
- **對話**：寬版主線；上方一條「子線狀態」列（背景工作數／卡住的）；緊急停止按鈕（保留
  `kill_switches`，因為是安全機制，不移除）。
- **監控**（唯讀）：ESP32 即時值＋最後回報時間＋過期標示；電腦端＝`work-context`、模型／
  TTS／麥克風／雲端開關、活動（`/v1/activities`）。每 3 秒輪詢，資料過期轉灰。
- 移除獨立的 任務／記憶／能力／設定／權限／系統／活動 入口。仍須保留者改成**對話內的卡片**
  （例：工具授權、記憶「我記住了這個」可就地撤銷）。技能審查與診斷的處理見 §5 D3。
- 這與 `docs/EXPERIENCE.md` 2026-10-15 的「對話、任務、記憶、能力、設定須有獨立可到達畫面」
  **衝突**，需先寫 `DECISIONS.md` 新條目取代，並更新依賴舊頁面 id 的證據腳本／測試。

### 3.2 後端：主線／子線
- 引入 `thread_id`（子線）掛在 `session_id`（主線）之下；主線只收子線的**摘要結果**與
  需要使用者決定的事。子線自帶 working memory、取消 token、預算，彼此不共用 prompt。
- 沿用現有 AgentRun／journal（RT-008）、取消傳遞（架構底線：取消須傳到 LLM／TTS／工具）。
- 每條連線一個 writer、佇列有上限：子線事件走獨立通道，不與主線 assistant_delta 混流。
- 背景來源盤點（`services/presentation/integrated.py`，全部寫入 `self._last_session` 即主線）：

  | 來源 | 進入點 | 歸屬 |
  | --- | --- | --- |
  | 自主研究筆記 | `share_self_note`（:375）← self_notes | 子線「研究」；主線只收一句摘要 |
  | 自動記憶通知「我記下了／要記嗎」 | `_auto_memory` :475/:481 | 主線，改為可就地撤銷卡片（現文案指向將移除的記憶頁，必改） |
  | 提醒到期／提醒意圖回覆 | `deliver_reminder` :492、:434 | 主線（使用者需要立即看到） |
  | 睡前回顧 | `daily_recap` :506 | 主線 |
  | 摸頭／戳／拎 | `_say_line(...,"touch")` :327 | 主線（是對使用者動作的即時回應） |
  | 感測器反應 | `_say_line(...,"sensor")` :371 | 子線「環境」；值得說的才上主線（沿用現有 `foreground_active` 擋） |
  | 規劃任務 `run_agent_plan` | :604，**在前景 turn 內同步執行** | 子線「任務」；主線立即回「開始做了」，完成回摘要 |

  `run_agent_plan` 目前會讓主線卡到規劃結束，是最需要拆出的一項。

### 3.3 後端：記憶自我整理
- Schema（需 migration，欄位可為空值以便回退）：新增 `tier`(core/archive)、`importance`(1–10)、
  `last_retrieved_at`、`retrieval_count`。沿用 `valid_to` 與 revision，不破壞既有來源／撤銷契約。
- 寫入閘門與層級規則見 §5 D1；`self_notes.remember_note` 與 `AutonomousMemory` 都改走閘門，
  不再直接 `remember`。
- 背景「睡眠」整理（Letta 式，非前景）：沿用 `MemoryOrganizer` 閒置生命週期，由它執行
  去重合併、升降級、淡出；前景對話搶占即取消；每次動作寫 revision＋原因，可撤銷。
- 使用者主權不變：仍可更正／刪除；更正後舊衍生結果失效（MEM-01 契約）。
- 隱私底線不變：敏感內容仍須確認；整理動作不得把 local-only 內容送雲端模型。

## 4. 分階段（一次只做一階段，做完停下回報）

| 階段 | 內容 | 風險 | 回退 |
| --- | --- | --- | --- |
| P0 | 本文審閱；寫 `DECISIONS.md`（取代 EXPERIENCE 舊決定）；列出舊頁面 id 被哪些測試／證據腳本引用 | 無 | 刪文件 |
| P1 | 監控頁＋唯讀系統端點（D2）＋對話頁瘦身骨架；新舊並存，舊頁尚不移除 | 低 | 還原 index.html／移除端點 |
| P2 | 記憶分層：migration、寫入閘門、self_notes 合併、背景整理器；先 **dry-run 只記錄「會怎麼處理」**，不真的寫，用真實資料檢查排序與合併結果後才開 | 中（核心＋資料） | feature flag 關閉；migration 欄位可為空值 |
| P3 | 主線／子線：thread_id、事件通道分流、背景來源歸屬 | 高 | flag 關閉回單線 |
| P4 | 移除舊頁面與 index.html 對應程式、更新證據腳本、真人走查 | 中 | git revert |

每階段驗收：先寫失敗測試再實作；WSL 以 `UV_PROJECT_ENVIRONMENT=~/.venvs/sirov2 UV_NO_SYNC=1`
跑 pytest；UI 以瀏覽器實測並截圖；不把未跑的命令寫成通過；STATUS.md 交整合者更新。

## 5. 已定案的設計決定（使用者授權「全部自己規劃」，2026-10-29；依據見 §1、§2）

- **D1 記憶不按時間刪除，改成兩層＋寫入閘門。**
  - 依據：Hermes 無時間衰減、額滿由代理合併；Generative Agents 衰減只用於排序；Mem0 在寫入時決定。
    沒有任何來源給出可直接套用的「短期保留 N 天」，所以不設 TTL，避免臆測數值。
  - **核心層**（每輪注入 prompt）：預算沿用 Hermes 實際值，SIRO 自身筆記 2,200 字元、
    主人資料 1,375 字元。超過 80% 時由背景整理器合併（Hermes 建議值）；額滿時不靜默丟棄。
  - **檔案層**（不注入、按需檢索）：其餘記憶全部保留，可用 FTS5＋向量搜尋，等同 Hermes 的 session search。
  - **寫入閘門**（Mem0 方式）：新候選先取最相近 10 筆，再由本機模型選 ADD／UPDATE／DELETE／NOOP。
    重複的「我自己查過…」會變成 UPDATE（合併主題、累計次數）或 NOOP。DELETE 依 Zep 改為失效：
    舊記憶 `valid_to` 設為新記憶 `valid_from`，保留 revision（沿用 MEM-01 契約），不做實體刪除。
  - **升降級**：用 Generative Agents 的三項分數（recency 0.995／小時、importance 1–10、relevance 餘弦）排序；
    升核心層另需過 OpenClaw 式三道門：分數、被檢索次數、被不同問題檢索到（多樣性）。門檻值官方未公開，
    P2 dry-run 以真實資料取分布後定案並記錄於 DECISIONS。recency 從「遊戲小時」改實際小時亦在此驗證。
  - **來源限制**：`siro.self-research` 等網頁衍生記憶只進檔案層，不升核心（OpenClaw 排除不可信候選）；
    使用者明確「記住…」直接進核心層且不自動降級（ChatGPT 已儲存記憶）。
  - 向量：本機已有 `qwen3-embedding:0.6b`（Ollama 實測列出）與 `adapters/models/ollama_embeddings.py`；
    無法取得時退回 FTS5 文字比對，閘門改為只做完全重複的 NOOP，不讓模型憑空判斷。
- **D2 電腦端數值：新增唯讀系統端點，CPU／記憶體／磁碟用 psutil。**
  - 依據：psutil 為 BSD-3、已在 lockfile（經 amqtt），不新增套件。文件沒說 `cpu_percent(interval=None)`
    是否阻塞，所以一律包在 `asyncio.to_thread`，符合「blocking I/O 不得卡 Core event loop」。
  - 這些數值只給監控頁看，**不送進模型 prompt**，避免未經同意擴大 SIRO 的觀察範圍。
  - 監控頁分兩區：「SIRO 實際知道的」（work-context、ESP32）與「電腦狀態（僅顯示）」。
- **D3 技能審查與診斷頁移除產品入口，不另設隱藏頁。**
  - 依據：Hermes 沒有對應的管理頁；使用者明確表示藏起來不算解決。
  - 技能安裝／啟用仍必須由人按一下，改成對話中的確認卡片，避免模型自行授權（架構底線）。
  - 健康狀態、模型路由、開關狀態放到監控頁；原始事件紀錄只保留在 `/v1/snapshot` API。
  - `/audio-field-test` 是獨立驗收工具，不在導覽中，維持原樣。
- **D4 子線看得到，但主線只收結果。**
  - 依據：Hermes 只把最終摘要放回父代理，桌面版在輸入框上方預覽最多 3 個 worker。
  - 對話頁輸入框上方顯示最多 3 條執行中子線（名稱、狀態、停止鈕）；監控頁列出全部。
  - 卡住判定沿用 Hermes 預設：450 秒無進展（工具內 1200 秒），之後中斷並回傳部分結果；數值做成可設定。
  - 併發：本機只有一個推論模型，背景模型呼叫一次一個，前景搶占。這依據現有 `_auto_memory`
    「不與回覆搶模型」的實作。Hermes 預設 10 個並行，不適用單 GPU 本機模型。
- **D5 刪除與復原沿用既有契約。** D1 沒有時間到期刪除，所以不需要另設「軟刪除 N 天」。
  使用者刪除與閘門 DELETE 都走現有 revision 機制，可在對話中說「把剛才那條記憶改回來」復原。
- **D7 主動發現要記什麼，不必說「記住」；說了就一定記。**（使用者 2026-10-29 要求）
  - 現況為何常漏記（程式碼證據，`core/memory_autonomy.py`、`core/memory_candidates.py`）：
    1. 模型只看到**單一句使用者原話**（`memory_nomination_prompt(text)`），沒有前後文；
    2. 每項必須是原話**逐字連續片段**（`statement not in text` 即丟），代名詞、跨句、改寫都抓不到；
    3. `_NONASSERTION` 含「可能／如果／例如／他說」等詞，片段中出現就整筆丟棄，誤殺真實陳述；
    4. 敏感內容不存，回覆要求使用者說「請記住：…」才存，正是使用者不想要的流程；
    5. 只看單輪，跨多次對話才浮現的習慣永遠不會被發現。
  - 明確「記住…」：沿用 `ingest_owner_request`，直接寫入核心層，不經閘門否決（只做去重合併）。
  - **主動發現 A：每輪抽取（Mem0 抽取階段）**：給模型「對話滾動摘要＋最近 10 則訊息＋最新一問一答」
    （Mem0 實驗 m=10；摘要由背景非同步更新，不拖慢回覆）。輸出可為改寫後的陳述，但每筆須引用
    來源訊息 id 與支持片段，程式核對片段確實出現在該則**使用者**訊息中（維持來源契約、避免模型捏造）。
    `_NONASSERTION` 由「片段含某詞即丟」改為交給模型標註是否為假設／轉述，並以正反例測試校正。結果進 D1 閘門。
  - **主動發現 B：反思（Generative Agents）**：近期事件 importance 總和超過門檻時，背景子線從多輪對話
    歸納習慣與偏好（論文門檻 150，以 1–10 分計；SIRO 對話量不同，P2 dry-run 取實際分布後定）。
    結果標 `inferred`（`ConsolidationCandidate.inferred` 已存在），先進檔案層，需過 D1 三道門才升核心，
    回覆時不得當成已確認事實。
  - 敏感內容：取消「要說請記住」。改成對話中一張卡片「要記下這件事嗎？保留／不要」，按一下即可。
    憑證類（密碼、token、驗證碼等 `_SENSITIVE` 中的憑證詞）一律不存，不提供保留選項。
  - 自動記下時，對話顯示「我記下了：…」小卡，附「不要記」可撤銷，沿用 `AutonomousMemory.undo`；
    現有文案「可在記憶頁刪除」改掉（記憶頁將移除）。
  - 驗收：建立正反例集（含代名詞、跨句、轉述、假設、敏感、憑證），在 P2 量測抓到率與誤記率後再開啟，
    數字照實記錄，不先宣稱目標已達成。
- **D6 權限開關保留**，因為是安全機制：對話頁一顆緊急停止（全部 kill switch），監控頁顯示各開關並可切換。

## 6. 不做

不 push、不開 PR、不部署；不動 ESP32 韌體與 TTS streaming；不新增套件（psutil 僅由間接改直接依賴）；
不用沒有來源的數值；不把 P0 文件當作已完成實作。

## 7. P0 需要更新的既有測試與證據腳本（舊頁面 id／路由）

`tests/integration/test_frontend_{goal_tasks,improvement_proposal,keyboard_skip,navigation,reflow,
skill_activation,skill_candidate,task_detail}.py`；`docs/evidence/` 下的歷史腳本屬已封存證據，不修改，
只在 DECISIONS 註明它們對應舊介面。P4 移除頁面時，同步改寫或刪除上列測試，並說明每個測試的去向。

## 8. 進度紀錄

- 2026-10-29 P1 完成：監控頁＋`/v1/system/stats`（commit ec2136a、8a038c6）。
- 2026-10-29 P2a 完成（試跑，不改記憶、不加 schema）：`core/memory_curation.py`（Mem0 四種操作＋分層規則）、
  `services/agent/memory_curator.py`（寫入後觀察、紀錄到 `$SIRO_DATA_DIR/memory-curation/dry-run.jsonl`，
  最多 500 筆）、`GET /v1/memory-curation`、`POST /v1/memory-curation/backfill`、監控頁「記憶整理（試跑）」。
  相近記憶目前用字元雙字組相似度（正式服務沒接向量檢索），已在紀錄的 `method` 欄註明。
  真實資料複本實測（gemma4:e4b，9 筆，皆為自主研究筆記）：ADD 7、UPDATE 2、NOOP 0、UNKNOWN 0；
  模型給研究筆記的 importance 為 7–9，**偏高且寬鬆**，同主題的「環境干擾」只合併 1 次。
  結論：P2b 真正啟用前須先調整判斷提示並以正反例集量測，不可直接開啟。
- 2026-10-29 P2b 完成（仍為試跑）：判斷提示 v2 依 Mem0 更新規則＋Generative Agents 重要度錨點；30 題合成案例 × 3 次，
  gemma4:e4b 正確率 v1 73/90 → v2 89/90，誤丟新記憶 0、誤刪 0。詳 [MEM-CURATION-P2b](../verification/MEM-CURATION-P2b/REPORT.md)。
- 2026-10-29 P2c 完成：可切換「試跑／套用」（預設試跑，存在 `$SIRO_DATA_DIR/memory-curation/mode`）。套用時 NOOP 把新的重複筆標為失效、
  UPDATE／DELETE 把被取代或被推翻的舊筆標為失效（`valid_to`，保留文字、來源與 revision）；明確「記住」的記憶依其決定性 id 辨識，永不自動處理；
  UNKNOWN、ADD、前景忙碌時不動。每筆可從監控頁「還原」（重新開啟並記 revision）。新 repository 方法 `set_valid_to`，未改 schema。
  已知限制：標為失效後只有帶 `as_of` 的檢索（對話 prompt 用的 `recall_context`）會排除；記憶頁搜尋與 browse 仍列出，P4 移除記憶頁時一併處理。
  真實記憶複本以 v2 試跑：9 筆 → ADD 3、UPDATE 6；其中「環境干擾案例」併入「情境感知／環境適應」屬跨主題，可能誤併，可還原。
- 2026-10-29 P3（a+b）完成：「規劃任務」改成子線，主線立刻回覆、完成後只回摘要（`IntegratedCompanion._start_plan_subthread`），
  一次只跑一件（單一本機模型）；背景整理器在規劃期間也讓路。自主研究筆記在主線只放一句，全文移到監控頁「背景工作／研究筆記」，
  SIRO 自己仍記得完整內容（`share_self_note(remembered=...)`）。對話頁已有「正在做什麼」側欄顯示進行中工作，不另加輸入框上方列。
  注意：P3 的 integrated.py／gateway.py／self_notes.py／index.html 修改有一部分被另一個執行緒的 commit f395045 一併提交（未經我測試）；
  本次 commit 補上其餘部分與測試，未改寫他人 commit。尚未做：提醒、睡前回顧、觸摸、感測器回應仍直接進主線（依 §3.2 表格屬主線）。
- 2026-10-29 P4 完成：導覽只剩「對話」「監控」。仍有用的功能原樣搬進監控頁：開關與權限（kill switch 可切換）、工作情境開關、
  SIRO 記得的事（搜尋／更正／刪除，保留使用者刪除權）、背景工作（含暫停與停止）、研究筆記、桌寵設定。刪除任務、技能、能力、電腦協助、
  系統診斷、個人檔案、閒置整理的畫面與前端程式（index.html 約 2855→2140 行）；後端 API 未刪。刪除 5 個只測已移除畫面的前端測試檔，
  其餘測試改為兩頁結構；`test_capability_product` 移除前端清單測試。相關 287 個測試通過。
  已知取捨：技能審查／啟用目前沒有畫面（D3 的對話確認卡片尚未做），技能功能本身未啟用；任務（讀檔目標）改由對話「規劃：…」使用。
- 2026-10-29 D7a 完成：自動記憶不再發「可在記憶頁刪除」文字，改為對話卡片「我記下了：…［不要記］」（呼叫既有 DELETE /v1/memories）。
  敏感個資（地址、健康、收入等）改為「要記下嗎？［保留］［不要］」卡片（POST /v1/memory-confirmations/{id}，每張只能答一次、一天後過期、
  最多同時 20 張，只存在記憶體，重啟即失效）；密碼、驗證碼、金鑰等憑證一律不存，也不提供保留選項。D7b（看前後文抽取）尚未做。
- 2026-10-29 D7b 完成：主動記憶抽取改看最近 10 則對話、可改寫並解開代名詞，但須附這一句的原話片段供核對；
  20 題合成對話 × 3 次（gemma4:e4b）量測後預設開啟（`SIRO_MEMORY_CONTEXT=0` 退回）。詳 [MEM-AUTONOMY-D7b](../verification/MEM-AUTONOMY-D7b/REPORT.md)。
  尚未做：D7 主動發現 B（跨多次對話的反思歸納）、D3 技能確認卡片。
