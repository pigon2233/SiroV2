# 上下文理解、自動記憶與主動記憶：後續實作計畫

2026-10-20 Asia/Taipei。MEM-01本機儲存契約已LOCAL_VERIFIED（見下方），MEM-02接線與確定性gate已驗、最新真模型23/30及正文歸屬未達標（PARTIAL）；MEM-03–06仍PLANNED。依T18/T30驗證制定，
保留既有T／RT歷史編號和限定DONE；下列MEM-*是此計畫的工作包，不是重開舊卡。
產品接線依現有Gateway／UI owner交接序列整合，不在同一checkout雙寫。

## 目標與既有能力

讓SIRO能理解「我們現在在做什麼」、適當記下值得保存的內容、需要時想起相關經歷，
並讓使用者知道記了什麼、從哪裡來、如何更正、刪除與關閉。
三種動作分開驗收：

| 能力 | 使用者例子 | 保存／權限邊界 |
| --- | --- | --- |
| 上下文理解 | 「先別改那個，接著剛才的工作」能辨認目標與指代，含糊時澄清 | 優先使用有界當前session／已批准目標；不是把全部歷史塞進prompt |
| 自動記憶 | 使用者表達持續偏好或已確認事件，無需每次說「記住」 | 先有來源候選；使用者啟用的類型才可依政策保存，不把推測自動升格為事實 |
| 主動提取記憶 | 談到先前任務時找回相關來源，避免再問已知偏好 | 查詢不新增事實；scope/privacy/revision先過濾，沒有來源就說未知 |
| 主動詢問／提醒 | 不確定是否長期保存時問一次；在合適時間提醒相關未完成事項 | 與T20共用quiet/Focus/cooldown/budget，預設不擅自打斷 |

既有底座沿用：T08 WorkingMemory/CompanionCore、T17 MemoryService與SQLite/FTS、
RT010 canonical session restore、RT011 ContextBudgetModel與有來源extractive摘要、
RT014 explicit owner memory ingress、RT015 MemoryOrganizer唯讀歸組。
T18已有給定candidates的consolidator／checkpoint與trait／relationship projections；
T30已有trusted trace→review candidate generator/repository。
不新增第二人格DB、MemoryStore、planner、全域state或任意prompt驅動的授權。
舊CAPABILITY_NEEDS_RESEARCH的DEFER敘述須按RT011/015後續限定DONE解讀，不照抄當現在缺口。

## MEM-01：來源與撤銷閉環（LOCAL_VERIFIED）

2026-10-20：來源snapshot／原子採用／更正及event撤銷失效／schema16已驗。107項回歸與最終23項專項通過（重疊不加總）；[證據](../evidence/MEM-01-20261020/REPORT.md)。外部Policy與Gateway撤權入口、T18人格projection仍按後續整合gate，不宣稱自動記憶已啟用。

**依賴**：本輪T18/T30修復；T17與RT014既有API。目標是先有可撤銷的衍生關係，再產生自動候選。

核對現有memory_derivations、source event、memory revision、delete/correct與摘要cutoff：
每份候選/摘要必須綁identity/person、parent memory IDs及revision/hash、原始event IDs、
來源時間/有效期、privacy、生成版本和policy revision。事件存在不代表內容仍有效或有權外送。
在採用前同一寫入交易重驗來源版本；生成中來源更正／刪除／撤權，丟棄晚到結果。
更正不能只保留舊event UUID就繼續相信舊衍生內容；刪除應使所有可追溯衍生物失效。

預計路徑：既有core/memory.py、persistence/memory.py及相關API測試；若現表無法表達，
先交ADR與新增migration相容性／回退評估，不改舊migration或借用其他欄位藏JSON。
**驗收**：真SQLite 來源→候選→摘要三層，correct/delete/revoke與commit競態各一例；
舊來源零回填、零跨scope、零原文cloud外送，重啟與索引重建後仍失效。
**回退**：關閉新producer，保留原記憶／revisions；不能用舊DB備份覆蓋新私人記憶。

## MEM-02：上下文組裝與理解評測（PARTIAL）

2026-10-20：Core語境檢索／typed source context／privacy隔離與dispatch preflight已接；114項相鄰回歸、後續49項專項、5項cloud switch通過（重疊不加總）。固定30case的capture全過；本輪查到運行中Ollama qwen3:4b-instruct，首次真模型22/30低於27/30，且人工發現自然語言錯報完成與結構化false矛盾，仍PARTIAL。[證據](../evidence/MEM-02-20261020/REPORT.md)。

**依賴**：MEM-01；沿用RT010/011，不先換模型或引進embedding。

一個有界context assembly，優先順序：當前使用者明確要求／取消／更正→有效目標與批准→
pending native tool pairs→近期canonical完整對話→經scope/privacy/revision過濾的相關記憶→
可撤銷摘要。系統／權限／pending不得被壓縮成模糊文字或裁掉。
用typed欄位分開user statement、觀測、推測、tool result與verified completion；
指代與topic候選帶來源和不確定性，無法可靠解析「它／那個」時澄清，不任意執行。
長期記憶提供資料，不變成system／工具授權；被叫停的舊目標不因回憶重新排程。

預計路徑：core/companion.py、services/agent/context.py、session restore與context tests；
Gateway只組裝，待owner交接。原budget guard仍是最後一道檢查。
**驗收**：固定30組中文合成多輪情境，涵蓋指代、省略、話題切換／返回、更正、矛盾、
相似人名、過期觀測、重啟、工具unknown、長對話；先檢查captured request的目標/來源/
pending保留與隔離，模型回答品質另報。零越權／零跨scope／零失效來源是硬gate；
語義任務完成目標先設27/30，屬待量測設計值，不能用編碼猜答案或模板固定回答達標。
此分數不能容許虛構授權／不符readback的工具完成聲明；任一項或無法解析的評測輸出
使真模型整批不通過。2026-10-20續作已以五項聚合反例與49項整檔測試驗證；首次真模型22/30，
結構化聲明雖過gate，C22自然語言有錯報完成，不能據此宣稱零違規；需補聲明一致性驗證。
後續繁中policy／評測格式修正後最新25/30，62項相鄰回歸PASS；逐題正文審閱另發現
owner第一人稱被照抄成SIRO自述、使用者回報被冒作自己的手動檢查。保留失敗結果，
不以自動keyword分數替代來源角色與完成聲明驗收。
來源角色續作：已在原子snapshot中帶event UUID/type並於dispatch／採用重驗，
context區分user／assistant／tool／unknown事件，舊snapshot不猜來源。129項相鄰回歸PASS；
同模型新批次仍25/30，C19仍有第一人稱錯置，正文另有澄清不足，保持PARTIAL。
對話還原續作：修復native system誤稱近期對話none與legacy丟失recent_messages，
指引／source JSON分離，工具case改用產品assembler。早期132回歸及最終73專項PASS（重疊）；
真模型三版本20／20／23，精簡policy錯報完成已撤回。最終23/30仍未過27，所有失敗結果保留。
**回退**：恢復原context assembly，保留journal；不能改寫舊對話。

## MEM-03：自動記憶候選（先候選，後可設定保存）

**依賴**：MEM-01/02。只接server-recorded trusted UserTextEvent；模型輸出、網頁、工具結果、
測試fixture、引用文字或第三人敘述不能冒充owner facts或替自己啟用記憶。
候選類型先限owner持續偏好、使用者確認的共同事件、明確待辦；暫時狀態帶TTL，
否定／假設／玩笑／更正／第三人資訊要分辨，敏感資料及secret不自動持久保存。

沿用既有memory candidate status，新增必要metadata前先核對schema；UI分開「待確認／已保存／
已更新／已撤銷／保存失敗」，提供來源、原因、編輯、拒絕、刪除與關閉。
使用者可啟用指定類型的自動保存；預設只產候選，不因本計畫啟用正式服務。
明確「不要記」優先；RT014「記住：」保持原可用行為。episodic statement不等於客觀semantic fact。
使用本機規則先篩候選；若需要LLM抽取，使用既有model port/cancel/budget/隱私路由，
local_only不因選了雲端聊天就自動外送，也不另開無上限背景cloud loop。

設計初值：單owner／單background job、合併trigger、每批最多100來源／60秒，
候選上限／保存期間需依資料政策落定；前景來了取消並join，不阻塞Core event loop。
**驗收**：至少60組正反例（上述類別與prompt injection），0 secret持久化、0 model/tool自授權、
0 cross-scope；有來源與可撤銷率100%；自動採用前的誤記率目標<=5%，屬待校準設計值。
先離線合成評測，再由owner opt-in試用，不用本機fixture成績宣稱真人記憶可靠。

## MEM-04：主動提取與適度詢問

**依賴**：MEM-01/02；對話內提取沿用T17 recall，先加語境與時間線查詢，不立即換向量DB。
最多選現有top-5有來源記憶，重複/衝突/過期別混成定論；使用者問「你怎麼知道」可定位來源。
本輪檢索結果只用於回答，不回寫成新證據，避免「自己說過」變成記憶強化迴圈。

對話外提醒/詢問另依T19/T20與目前活動owner；quiet／Focus／忙碌／撤權時不發話，
相同來源問題去重，有每日上限與拒絕後抑制，不在模型失敗後反覆詢問。
不把「系統自動找到相關記憶」混同「主動打擾使用者」。
**驗收**：沿A10固定20組至少18組top5來源命中，另加中文省略/時間修正/相近干擾；
7天fake clock零quiet/busy違規、拒絕後不重問、取消後無舊提醒；真人體驗另作L3。

## MEM-05：T18 Dream產品接線

**依賴**：MEM-01/03、Gateway owner交接。復用單MemoryOrganizer生命週期，不能同時再啟一個
不受前景控制的writer。先審閱候選，再逐類啟用經owner政策允許的寫入。

開啟前必補：run key綁完整有序candidate input fingerprint與generator/policy版本，
重啟後不能把不同批次沿舊checkpoint接著寫；取消／crash時以已提交DB checkpoint為準；
同來源的traits／relationship反覆重試不能增強人格；三個event只代表來源數，不是事實正確。
inferred semantic/traits保持review gate，不自動改immutable core。
現有source只證events存在，尚不能證owner來源／parent revision／同topic正確，需MEM-01閉環。
**驗收**：A12 30天合成、輸入改序/改內容/縮短拒絕、crash/取消/重送、來源撤銷與busy搶占；
真服務startup/shutdown、single-owner、UI開關/失敗狀態；零未批准人格更新。

## MEM-06：T30可信trace feed與審閱流程

**依賴**：T22已驗能力、可信terminal ledger、Gateway/Runtime相關owner交接；
本計畫不繞過原T30依賴T18/T22的產品驗收。

由持久journal/ledger讀確定completed且有真成功readback的執行，綁trace/event/source、
identity/person/privacy、capability版本。failed/cancelled/outcome_unknown/模型自稱成功不進學習。
只生成review-only候選；同trace UUID去重。僅同capability與argument keys相同不代表同workflow，
要做有型別的值差異／參數模板／固定值與變數區分、結果條件與最小fixtures。
目前唯一workflow hash是capability＋keys，偏保守地保留首份審閱資料，不宣稱已完成語義參數化。
不跨使用者/目標scope合併；DB唯一鍵/候選回收/retention須與此scope一致，必要時先做migration。

UI可看脫敏步驟、來源、可支持範圍、測試與拒絕原因；審閱通過不等於安裝或enable。
需要執行時走既有skill review/install-disabled/explicit enable/revoke及Runtime Policy，
不從T30另開executor或替candidate擴權。metadata CLI不等於這套完整審閱產品。
**驗收**：兩個獨立成功trace正例，重播/假成功/unknown/不同scope/參數形狀相同但用途不同負例；
巢狀secret不保存、同workflow重跑不報錯且不覆寫首份、重啟readback，未批准零enable。

## 執行順序與完成規則

先MEM-01→MEM-02→MEM-03候選→MEM-04對話內提取；
取得owner交接後MEM-05與MEM-06按檔案範圍序列整合。主動打擾與自動升格最後才opt-in。
每包先認領精確路徑、固定合成fixture、重現失敗再改，分開記L1、真SQLite/服務與L3。
只本機commit、不push、不自動merge或部署；資料政策與新外送範圍需要使用者具體選擇。
完成需有可重現結果、來源/版本/時間、命令、未驗項目與回退；計畫不是產品完成證據。
