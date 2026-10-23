# 記憶產品接續：沿用 RT 與 Hermes 借鏡

2026-10-21 Asia/Taipei；PLANNED / NOT ENABLED / LOCAL_ONLY。
使用者已要求把本輪 RT 核對與 Hermes 借鏡納入後續計畫。
本文件是 [MEM-01–06 計畫](PLAN.md) 的接續細化，不新增或重編 RT／RI 任務，
不把計畫納入當成實作、整合、啟用或發布完成。

## 現況與證據範圍

本計畫以記憶分支 `b57c7d28e764ba4556adfb76d6324dcd9291c9b3` 為基線。
2026-10-21 唯讀盤點的 main 為 `eeb0cba81d0115d1449df73f7342b98c6c39bc3c`；
後續 fetch 的 origin/main 為 `60af7f1fa2ccf76be63d89b33c90da9590725e0e`。
分支程式存在不代表正在運行的服務已載入；未檢查私人 DB 或重啟服務。
RT 歷史證據按原限定範圍保留，本輪沒有重跑 RT／模型／真人驗收。

| 底座 | 已有能力與入口 | 本輪接續邊界 |
| --- | --- | --- |
| RT-008 | AgentRun／journal 持久紀錄、未知結果與恢復 | 供查證已發生的事件；不能因恢復對話重播副作用 |
| RT-010 | bounded completed dialogue restore；`services/agent/runs.py` | 沿用近期恢復；跨 session 歷史檢索另驗，非無限歷史回放 |
| RT-011 | `services/agent/context.py` 預算、`summary.py` 有來源摘錄 | 保留目標、權限、pending；摘要不等於語義理解或長期事實 |
| RT-014 | `MemoryService.ingest_owner_request` 明確「記住」入口 | 保留原可用流程；不把它宣稱成廣義自動抽取 |
| RT-015 | `MemoryOrganizer` 單一生命週期、有界唯讀歸組、前景 cancel/join | 延伸前先核對 caller；不是自動寫 facts，也不是 companion 主動訊息 producer |
| RI-002／004 | catalog inventory、部分技能候選／審閱／受限 worker 切片 | T30 沿現有 registry／Runtime Policy 接線；不是任意生成技能均已驗證 |
| MEM-01／03-A/B/C | lineage、來源接納、規則草稿、原子候選審閱與 action readback | 多為合成來源／注入 Policy 的本機驗證；真 Auth／owner／Policy adapter 與 UI 尚待整合 |
| MEM-04／04B | SQLite 可選向量索引、原文來源篩選與後置重驗 | 未接正式聊天；不把 698 項元件回歸當整體產品完成 |

狀態依據：[RT roadmap](../runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md)、
[Runtime Intelligence 設計](../runtime-evolution/RUNTIME_INTELLIGENCE_DESIGN.md)、
[MEM04B 實測](../verification/MEM04B-relevance/REPORT.md)。歷史段落的 DEFER／缺口
可能已被較新限定完成紀錄取代，不因舊表格再開一套 framework。

## Hermes 借鏡與採用決定

原 [Hermes 比較](../runtime-evolution/HERMES_GAP_ANALYSIS.md) 固定在
`f42f579cf8bac4918ac9599bece71618afadd846`，不是下列現行文件的版本保證。
現行官方文件於本對話 2026-10-21 查閱，只作設計參考；未執行、安裝 Hermes 或新增依賴。

| 借鏡 | SIRO 採用方向 | 不直接照搬的行為 |
| --- | --- | --- |
| 精簡持久記憶與歷史搜尋分離 | 少量相關常用偏好＋近期對話＋按需來源檢索 | 不新增平行 MEMORY.md／USER.md 作產品真實來源，不把全部歷史塞入每輪 prompt |
| session frozen snapshot／prefix cache | 穩定序列化、版本鍵、相同有效來源可重用 | 更正、刪除、撤權、到期須在當前 session 下一次使用前失效，不能等新 session |
| memory／skill 寫入審核 | 待審、預覽／diff、批准、拒絕與目標版本核對 | 不沿用自由自動寫入預設；不讓模型宣稱已保存代替 transaction readback |
| skills progressive disclosure | 清單摘要→所需完整技能→指定參考檔，逐層計預算 | 不把模型載入文件當授權、安裝或啟用 |
| 背景學習與有界排程 | 沿 RT-015 owner 與既有活動控制，低優先候選、前景搶占 | 不新增不受控制的 scheduler，不把候選學習和主動打擾合併啟用 |

官方來源：[Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)、
[Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)、
[Scheduled tasks](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)。
上述是參考機制；SIRO 的權限、資料分類與可撤銷來源契約保持優先。

## 工作切片與驗收

下列名稱是 MEM 原卡的子切片，不取代既有 T／RT／RI 編號。數值若非已有證據，
皆為設計門檻或待量測值，不是已達成果。正式啟用不豁免 MEM-02 27/30 與安全硬 gate。

### MEM-02：整合與理解品質

依賴：MEM-01、RT-010/011、Gateway／UI owner 的明確交接。
先盤點本機分支／schema 16–18 與當前 main 差異，序列整合，不在 dirty main 搶寫。
沿用現有 context assembler／MemoryService，加入可選檢索裝配及使用者可理解的不可用狀態。
新資料目錄、舊 schema 升級、重啟、備份還原與相容 reader 均須驗；程式回退不能覆蓋新記憶。

驗收：中文固定 30 組至少 27 組，另凍結未見案例；分開評人物、指代、衝突、澄清、
工具完成聲明與回答來源。零跨 scope／失效來源／虛構授權／假完成是硬 gate。
目前最新 25/30 及角色錯置不因改計畫而解除；缺證據要澄清或說未知。
回退：關新裝配、保留 journal 與 revisions，不改寫歷史對話。

### MEM-04：分層載入與跨對話查找

依賴：MEM-01/02、RT-008/010/011、MEM04B optional retriever；產品啟用仍須整合驗收。
先量測常用偏好投影與現有檢索組合，再決定是否省略不必要的分類呼叫；不以固定關鍵字
猜答案繞過相關性判斷。不預設全部偏好必須每輪注入，也不假設 prefix cache 等於免費。
常用偏好、事件事實與任務技能分開，矛盾與來源身分不在壓縮時消失。

跨 session 歷史先用既有 conversation／journal 做唯讀有界查詢，回傳最少片段、
來源 session/event、角色、時間、privacy 與版本；適配現有記憶及摘要失效規則。
歷史 assistant 自述不是 user fact，歷史 tool intent 不是成功 readback；查詢不恢復執行。
若既有索引不足，先以實際查詢收益／成本及契約決定，不能直接新增第二向量 DB。

驗收：原 20 題 top-5 至少 18 命中，保留原缺來源題，新增跨 session、相似人名、
過期事件、引用、矛盾、來源撤銷與注入負例；另以凍結盲測報漏記及多餘來源率。
同 session 更正／刪除／撤權／到期及分類等待期間變更，快取與後續 prompt 均不得用舊來源。
來源需可定位，檢索後仍過最終 context budget；無授權不得讀另一 scope 歷史或送 cloud。
回退：關歷史查詢／常用投影／可選篩選，沿既有近期上下文；無新歷史副作用重播。

成本驗收須用同題、同模型／digest、同來源與冷熱條件，比較原字詞、向量、向量加分類、
分層方案。分列 embedding、分類輸入／輸出、聊天輸入／輸出、失敗未知用量、快取命中及淘汰，
量測延遲 p50/p95、RAM／VRAM 與品質；樣本數／硬體／常駐狀態須明示。
不能用單案例約 60% 節省或立即重問零分類 token 宣稱日常平均、最低成本或 SLO 已達。

### MEM-03：可審閱保存與資料生命週期

依賴：MEM-01/02、MEM03A/B/C、真實 Auth／owner／Policy lease adapter。
接 server-recorded owner 來源，不補造舊事件 marker；MEM03C transaction 與 lease 到提交結束
的語義保留。提供待確認、已保存、已更新、已撤銷、保存失敗／結果未知的清楚狀態。
預覽顯示來源／理由／類型／保存期，編輯、批准、拒絕、刪除、關閉與按類型 opt-in 都可操作。
模型口頭說「記住了」不能產生已保存狀態；timeout／取消後依 action UUID 查結果，不能盲重送。

驗收：原至少 60 組正反例及規則基線保留，新增未見敏感說法與多人語境；
來源／可撤銷率 100%、零 secret 新增持久化／模型自授權／跨 scope，真人誤記率另校準，
<=5% 是原設計目標，未測不能宣稱達成。批准後來源變更／撤權／重試／重啟均需 readback。
區分來源原事件原已保存與本次候選新增寫入，不能以草稿不寫 DB 宣稱入口完整 DLP。
回退：停新 producer／writer，保留既有記憶與審閱紀錄；撤回已採用資料走原來源撤銷流程。

同切片必落實 retention／deletion：說明目前操作影響記憶、向量索引、摘要、候選、
raw conversation、revisions 與備份的哪幾層；可配置期限與清除結果不得只顯示「已刪除」。
驗更正／刪除／到期後重建索引、重啟及舊備份還原的行為；備份仍含資料須告知到期範圍，
不得把 recall 隱藏或 TTL 失效冒稱 SQLite／備份物理 purge。資料政策變更先交 owner 決定。

### MEM-05／MEM-04 對話外提醒：沿 RT-015 生命週期

依賴：MEM-01/03、T18/19/20、RT-015、目前活動與 Gateway owner 交接。
延伸既有單一 owner、coalesced trigger、有界 batch、前景 cancel/join、shutdown 清理。
目前 RT-015 最多 100 來源／5 秒唯讀歸組，不把它當成已驗 100 來源／60 秒自動寫入；
writer、模型成本與取消窗口要另測。Dream 的有序批次 fingerprint、checkpoint、來源撤銷與
traits／relationship 冪等按原 MEM-05 驗，禁止反覆重試強化人格。

主動提醒單獨 opt-in：quiet／Focus／忙碌／cooldown、每日上限、拒絕後抑制及同來源去重。
使用者能停一件事、關閉自動整理與停止背景工作；無 readback 不可顯示停止成功。
與目前活動 producer 序列整合，不只因已有 ProactivityRules 類別就宣稱已接 companion。
驗收：原 A12 30 天合成、七天 fake clock 零 quiet/busy 違規，前景打斷／撤權／斷線／重啟
不復活舊提醒，單一 owner 無殘留 task、無未批准人格寫入；真人干擾率另驗。
回退：停新增 producer、取消並 join，保留來源與 checkpoint，不重播待送效果。

### MEM-06：T30 技能記憶按需載入

依賴：T18/T22、可信 terminal ledger、RI-002/004 與 Runtime owner 交接。
從有成功 readback 的 trace 生成 typed workflow 候選，保持來源／scope／capability 版本。
清單先載名稱、用途、必要權限、可用性；選中才載完整步驟與指定參考，所有階段都計入 budget。
摘要、來源文件與技能內容是資料，不是新的系統授權；不因載入就安裝、enable 或執行。
審閱顯示 diff、測試、固定值／參數、來源與目標版本；批准前變更須重新審核。

驗收：兩個獨立成功 trace，failed/cancelled/unknown／偽成功／不同 scope 不進學習；
相同參數形狀但用途不同不錯合併，巢狀 secret 不保存。冷／熱多技能場景證明未選技能正文
不入 prompt，必要引用完整；舊版本、撤銷、注入、超限與取消負例通過；
候選批准不等於執行權限，enabled/revoke 仍經原 SkillRegistry／Policy／Runtime。
回退：停新 trace feed／載入器，保留 disabled candidates；不新增 executor 或第二技能 registry。

## 開發輔助、執行順序與正式可用 gate

[Codebase Memory](../runtime-evolution/CODEBASE_MEMORY_INTEGRATION_REPORT.md) 屬開發期原碼圖譜。
可幫查 caller／影響範圍，但原報告安裝在另一台 Linux 路徑；不代表本 Windows／WSL 已裝好或
此對話已接 MCP。先核對平台、binary hash、source manifest、排除規則與過期索引，再使用；
不能索引私人聊天／DB／keys，也不能把程式圖譜當使用者記憶或 runtime 權限。
沒有條件時沿 rg／AST／測試查證，不為此先裝全套工具。

執行順序：

1. 凍結 main／記憶分支差異與 owner 範圍，列 schema 相容性與整合回歸；保持已有 RT DONE。
2. MEM-02 補理解失敗與裝配；可先做互不依賴的唯讀／UI 準備，但不繞過正式啟用 gate。
3. MEM-04 分層／跨對話查詢與 MEM-03 審閱流程按檔案分工序列完成，先提供人工確認試用。
4. MEM-05 背景保存及對話外提醒逐類 opt-in；MEM-06 按原依賴接成功 trace 與技能審閱。
5. 通過來源／權限／隱私硬 gate、凍結模型品質、真服務重啟取消、資料遷移／備份還原、
   成本延遲與真人記憶流程後，才宣稱相應能力正式可用。

整套發布仍依 [ACCEPTANCE](../ACCEPTANCE.md) 的乾淨安裝、真音訊／body／OS 範圍、
24 小時運行、三輪真人體驗與正式回退演練，不用本計畫或元件測試解除。
共享 STATUS／DECISIONS／RT roadmap 由整合 owner 更新；本卡只補本對話記憶計畫。
本機 commit、NOT PUSHED；文件回退只撤本卡文件，不動 DB、服務、模型或其他人的成果。
