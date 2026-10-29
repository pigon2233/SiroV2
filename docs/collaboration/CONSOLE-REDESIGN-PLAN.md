# CONSOLE-REDESIGN-PLAN：控制台重造、記憶自我整理、主線／子線對話

Owner：Claude（thread「siro 製作」）；2026-10-29；狀態：PLAN ONLY / LOCAL_ONLY / NOT PUSHED。
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
- Generative Agents（Park 等，2023）<https://arxiv.org/abs/2304.03442>：
  摘要頁只確認有「觀察→檢索→反思→規劃」；**檢索公式與衰減係數我沒能取得全文確認**，
  不引用具體數值。實作前須讀原文第 4.1 節再定，不憑記憶設定。
- SCM（睡眠整合＋刻意遺忘）arXiv 2604.20943 僅為近作旁證，未驗證，不作設計依據。

結論：沒有任何一個參考系統證明「某個固定半衰期最好」，所以衰減參數必須由 SIRO 自己的
實測資料校準，不能先寫死數字（見 §5 驗收）。

## 3. 目標設計

### 3.1 前端：兩個畫面
- **對話**：寬版主線；上方一條「子線狀態」列（背景工作數／卡住的）；緊急停止按鈕（保留
  `kill_switches`，因為是安全機制，不移除）。
- **監控**（唯讀）：ESP32 即時值＋最後回報時間＋過期標示；電腦端＝`work-context`、模型／
  TTS／麥克風／雲端開關、活動（`/v1/activities`）。每 3 秒輪詢，資料過期轉灰。
- 移除獨立的 任務／記憶／能力／設定／權限／系統／活動 入口。仍須保留者改成**對話內的卡片**
  （例：工具授權、記憶「我記住了這個」可就地撤銷）。技能審查與診斷是否保留 → 見待決 Q3。
- 這與 `docs/EXPERIENCE.md` 2026-10-15 的「對話、任務、記憶、能力、設定須有獨立可到達畫面」
  **衝突**，需先寫 `DECISIONS.md` 新條目取代，並更新依賴舊頁面 id 的證據腳本／測試。

### 3.2 後端：主線／子線
- 引入 `thread_id`（子線）掛在 `session_id`（主線）之下；主線只收子線的**摘要結果**與
  需要使用者決定的事。子線自帶 working memory、取消 token、預算，彼此不共用 prompt。
- 沿用現有 AgentRun／journal（RT-008）、取消傳遞（架構底線：取消須傳到 LLM／TTS／工具）。
- 每條連線一個 writer、佇列有上限：子線事件走獨立通道，不與主線 assistant_delta 混流。
- 先決條件：盤點哪些背景來源目前寫進主線（self_notes、goal-tasks、tool proposals、
  sensor_reactions、proactivity），逐一決定歸屬哪條子線。**此盤點未做，故不估工時。**

### 3.3 後端：記憶自我整理
- Schema（需 migration）：新增 `tier`(short/long)、`importance`(0–1)、`last_used_at`、
  `use_count`、`expires_at`。沿用 `valid_to` 與 revision，不破壞既有來源／撤銷契約。
- 寫入閘門：寫入前以去重（正規化文字＋向量近似，沿用 MEM-04 向量索引）與價值判斷擋掉
  例如重複的「我自己查過…」；`self_notes` 改為**合併進同主題一筆並累加次數**，不再每次新增。
- 層級規則：新記憶預設 short（有 `expires_at`）；被反覆使用／反覆出現／使用者明確要求
  才升 long；短期過期**軟刪除**（保留 revision 與來源，可由使用者復原）。
- 背景「睡眠」整理（Letta 式，非前景）：沿用 `MemoryOrganizer` 閒置生命週期，由它執行
  去重合併、升降級、淡出；前景對話搶占即取消；每次動作寫 revision＋原因，可撤銷。
- 使用者主權不變：仍可更正／刪除；更正後舊衍生結果失效（MEM-01 契約）。
- 隱私底線不變：敏感內容仍須確認；整理動作不得把 local-only 內容送雲端模型。

## 4. 分階段（一次只做一階段，做完停下回報）

| 階段 | 內容 | 風險 | 回退 |
| --- | --- | --- | --- |
| P0 | 本文審閱；寫 `DECISIONS.md`（取代 EXPERIENCE 舊決定）；列出舊頁面 id 被哪些測試／證據腳本引用 | 無 | 刪文件 |
| P1 | 監控頁（唯讀）＋對話頁瘦身骨架；新舊並存，舊頁尚不移除 | 低（只讀既有端點；Q2 若要 CPU 則加唯讀端點） | 還原 index.html |
| P2 | 記憶分層：migration、寫入閘門、self_notes 合併、背景整理器；先 **dry-run 只記錄「會怎麼處理」**，不真的刪，供使用者檢視 | 中（核心＋資料） | feature flag 關閉；migration 欄位可為空值 |
| P3 | 主線／子線：thread_id、事件通道分流、背景來源歸屬 | 高 | flag 關閉回單線 |
| P4 | 移除舊頁面與 index.html 對應程式、更新證據腳本、真人走查 | 中 | git revert |

每階段驗收：先寫失敗測試再實作；WSL 以 `UV_PROJECT_ENVIRONMENT=~/.venvs/sirov2 UV_NO_SYNC=1`
跑 pytest；UI 以瀏覽器實測並截圖；不把未跑的命令寫成通過；STATUS.md 交整合者更新。

## 5. 待使用者決定（我不臆測）

- **Q1 記憶保存期限**：短期預設保留多久？我不預設數值，建議 P2 先 dry-run 一週，用實際
  使用資料再定；你若已有偏好請直說。
- **Q2 電腦端數值**：只顯示 SIRO 實際取得的（work-context／模型／活動），還是要新增
  CPU／記憶體／磁碟的唯讀端點（新功能，需新增 psutil 類依賴或自寫讀取，須先核實授權）？
- **Q3 技能審查／診斷頁**：全部移除，還是保留在不顯示於導覽的 `/#/advanced`？你說藏起來
  不算解決，所以我預設**移除產品入口**；診斷資料改為監控頁的一小區。
- **Q4 子線可見性**：背景子線的過程要使用者看得到（監控頁列出），還是只在完成時回報主線？
  預設：監控頁可看、主線只收結果。
- **Q5 刪除的容忍度**：短期記憶過期後「軟刪除、可復原 N 天」可以嗎？

## 6. 不做

不 push、不開 PR、不部署；不動 ESP32 韌體與 TTS streaming；不新增依賴（除非 Q2 決定並核實）；
不用固定半衰期等未經校準的數值；不把 P0 文件當作已完成實作。
