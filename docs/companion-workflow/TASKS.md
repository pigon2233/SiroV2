# 施工卡、依賴與驗收

所有卡初始狀態 **PLANNED**。CP 編號只屬本計畫，不重新編排既有 T／RT。
每卡須在開始時重新核對實作、caller、consumer、配置、MUST NOT CHANGE 與 owner，
在結束時交 commit SHA／檔案／測試結果／限制／回退，未完整驗收不可標 DONE。
「雙方」表示兩份各自有 owner 的產出，不表示同時修改同一檔案。

## 依賴總表

| ID | 負責人 | 交付 | Depends on |
| --- | --- | --- | --- |
| CP-00 | Codex＋Claude，各自產出 | 基線、檔案認領、契約接收、測試資產與平台確認 | — |
| CP-V01 | Codex | 現有動作盤點、自然度基線、鏡頭與動作分鏡 | CP-00 |
| CP-V02 | Codex | 現有 rig 動作／過渡／channel 資料包與預覽 | CP-V01 |
| CP-V03 | Codex | 原創全身設計、分層及 Editor 匯出工具鏈 | CP-V01 |
| CP-V04 | Codex | 可編輯全身 rig、首批完整活動資產包 | CP-V03 |
| CP-V05 | Codex | 氣泡與活動監測頁的畫面／狀態／響應式稿 | CP-00 |
| CP-P00 | Claude | T10 已知取消／刷新、放大與記憶問題修復並重驗 | CP-00 |
| CP-P01 | Claude | 素材載入、動畫混合與可打斷狀態接線 | CP-P00, CP-V02 |
| CP-P02 | Claude | 真工具／網路活動紀錄、持久讀回與狀態契約 | CP-P00 |
| CP-P03 | Claude | 監測頁、氣泡狀態、查看／停止／暫停功能 | CP-P02, CP-V05 |
| CP-P04 | Claude | 有界自主活動、興趣來源、安靜模式與研究筆記 | CP-P01, CP-P03 |
| CP-P05 | Claude | 有 scope 的工作情境／可選畫面觀察 adapter | CP-P04 |
| CP-P06 | Claude | 全身步態＋桌面位置／命中／邊界整合 | CP-P01, CP-V04 |
| CP-I01 | Codex 視覺；Claude 程式 | 全流程整合與 owner 試用驗收 | CP-P05, CP-P06 |
| CP-I02 | Claude 準備；授權整合者操作 | 發布、相容性、備份還原與部署回退驗收 | CP-I01 |
| CP-O01 | Claude，選配 | 程序層網路覆蓋補強 | CP-P03 |

V 線可在 P00 修復期間製作資產／畫面，不進入正式程式；P04 自主探索不得跳過 P00／P03。
O01 非第一版 blocker；若未做，監測頁須明確揭示未覆蓋程序流量。
表中的 dependency 代表該卡的完整驗收前置，若外部 rig 工具鏈卡住，保留可用的現有模型
與監測／自主研究限定成果，不把全身或整體專案標完成。

## 卡片細節

### CP-00：協作與契約基線

- Codex：提交視覺／契約草案與預定素材路徑；Claude：提交 runtime path／觀測能力／配置核對。
- 雙方在 GitHub 留接收回覆及各自 owner／branch／base SHA／精確 owned paths。
  若 Issue／PR 權限未修復，保留 pushed branch 與明確待交接，不當共享鎖。
- 核對單 writer、BodyAdapter、Core affect、speech owner、journal、browser session、proactivity caller。
- 驗收：契約欄位對映到實際 caller／consumer；不存在之 API 標為提案，沒有未指定 owner 的共享檔。
- 回退：撤規劃 commit，不更動生產狀態。此卡不自動接受任何後續 protocol migration。

### CP-V01：動作問題盤點

- 交付現有 parameter／motion／expression 清單，型別、範圍、可用性、來源／授權與 SDK 版本。
- 錄待機→注意→說話→情緒變化→停止→恢復；記錄哪些姿勢跳變、呼吸中斷、視線或嘴型衝突。
- 分鏡列 entry／loop／exit／interrupt／resume；以現有 rig 的實際支援為限。
- 驗收：每個缺陷有重現與對應參數，不以「不自然」籠統帶過。回退：僅撤設計資料。

### CP-V02：現有模型自然過渡包

- Codex 製作曲線、淡入淡出、主動作與微動作的混合規格；初值可用 0.2–0.6 秒試調，
  這是待驗設計值，不是 SDK 強制值或已量測成果。
- 支援注意、點頭、思考／閱讀姿態、待機、說話姿態及回到原活動；缺姿勢須標 unsupported。
- 交付 channel mask、參數白名單、固定 seed 預覽情境、相容 hash；不改 production 程式。
- 驗收：Claude 載入後可重現，反覆切換不從零跳回，不干擾 Core 表情與真音訊嘴型。
- 回退：停活動切回舊資產版本；不能透過停止所有 motion 清掉表情。

### CP-V03：全身設計與工具鏈

- 產物：角色比例／左右朝向／服裝／色票、至少站立與坐姿參考、遮擋關係、分層計畫。
- imagegen 可產候選；身份一致與可綁定性要檢查。外觀草案先給使用者看，再大量製作。
- 必須確認 Windows／macOS 可用 Editor、工程取得與匯出往返；列清楚哪個操作能自動、哪個需人工。
- 驗收：一份簡單工程可編輯→匯出→真 renderer 播放；概念圖完成不等於此卡 DONE。
- 缺環境：BLOCKED 並保留已做圖稿，不換成假模型。回退：不取代目前可用角色。

### CP-V04：完整活動資產

- Codex 完成 rig、左右步態、起停／轉向、坐起、注意／揮手、筆記本拿出／閱讀／收起。
- 每個資產帶 entry／exit 姿勢、loop／interrupt 條件、接地點、參數、channel、duration 與來源。
- 驗收：關節／衣物不破圖、左右身份一致，真步態有腳步而非站姿平移；交可編輯工程及 runtime 包。
- 回退：舊模型保持可選且驗證相容；不能回退人格／記憶。發布的 binary 要有合法來源與存取方式。

### CP-V05：活動監測畫面

- Codex 交桌面、320px、200% 實際縮放的參考稿／標註；狀態不限成功，含等待／失敗／取消中／
  未確認／斷線／空清單／超長目標／無權限，並有鍵盤與讀屏語意規格。
- 小氣泡只呈現短狀態；詳細頁顯示時間軸、發起者／原因、工具與網路目標、結果、產物與覆蓋說明。
- 驗收：新手能指出現在在做什麼、為何、是否成功，以及如何停止；不把 phase 裝飾成實際執行。
- 回退：設計稿可獨立撤回；production HTML/CSS/JS 由 Claude 實作，不雙寫。

### CP-P00：先解決已有失敗

- 讀最新真人彙總與正在修復的 source，不重複實作別人的 dirty 修復。
- 取消：核對 tool run／turn、真正終止／unknown、卡片終態；刷新後舊「等待完成」不得觸發新文字／語音。
- UI：實際 Firefox 200% 技能／設定可點，恢復比例也正常；記憶：已存／不可讀／沒有匹配分清。
- 驗收：先前失敗場景有最小動態回歸＋真 owner 重測；新 turn 保持可用，不能關掉 fence 通過。
- 回退：精確 fix commit，保留證據與資料。不以寫更多報告替代修復。

### CP-P01：視覺程式接線

- Claude 在 presentation adapter 接 V02，不讓 Core 知道每個骨骼／像素；沿用單一 body／audio owner。
- 每個活動有 instance／generation，過期 callback 拒絕；動畫本地逐幀，runtime 低頻選意圖。
- 驗收：motion／expression／gaze／mouth 不衝突；相同意圖去重、loop／interrupt 不死等完成回呼，
  asset 缺項明示 fallback，不偷偷換角色；停止移動不打斷另一個有效說話。
- 回退：新表現可停用，舊 body.v1 與角色仍可用；不改情緒／記憶格式。

### CP-P02：活動與網路實際紀錄

- Claude 依 CONTRACTS 實現；實作前核對現有 journal／API，優先 adapter／投影，避免雙 DB owner。
- 在實際 dispatch／完成邊界記錄；browser redirect／cache 等由可用 adapter metadata 提供。
  arbitrary shell 未涵蓋的網路明示 unknown，不能解析命令字串冒充完整網路監測。
- 驗收：受控本機 HTTP 故障情境、競態停止、亂序／重送、斷線補讀、進程 crash／重啟、儲存故障。
  日誌脫敏，分頁／buffer／retention 有界；audit 不可用時不啟動新的自主外部操作。
- 回退：先停止 producer，自主性關閉，保留 journal；新增 migration 必須驗舊版讀取相容。

### CP-P03：活動監測 UI 與控制

- Claude 依 V05 做正式 UI；快照＋cursor 消費真資料，不重播執行／TTS，不以瀏覽頁觸發模型。
- 停止指定 activity，暫停自主排程，全部背景停止各有語意，不能誤停有效前景工作。
- 驗收：工具列表對應真紀錄，terminal 狀態單調，未知可見；200%／鍵盤／讀屏、斷線／溢出／長字串，
  refresh 及過期控制不誤操作；可確認快取與真連線的差別。
- 回退：可關新頁而不改既有聊天；資料 producer 停用策略與 P02 一致。

### CP-P04：自己的活動與研究

- Claude 接興趣來源、候選選擇、既有 budget／proactivity、一次一背景 run、checkpoint／研究筆記。
- 動畫與真研究分離；可以做自己的事，也能選擇等待。當次失敗不造來源，不無限再排。
- 驗收：真受控網站研究→監測可見→有來源筆記→合適時機分享；被叫回即讓前景優先，
  停止／重啟不重做已完成副作用，無預算不跑 background cloud，研究內容不污染 owner facts。
- 回退：關閉自主選擇／producer，保留使用者對話與既有紀錄；不清記憶。

### CP-P05：理解使用者當下情境

- Claude 先接可信任務／使用者分享情境，再做有 scope 的活動應用 metadata／選定畫面觀察。
- 每筆 observation 有來源／時間／期限／privacy／permission revision；關閉即停止取得與使用失效內容。
- 驗收：看到編輯器只推測正在寫程式，Focus 不打擾；未知、錯判更正、來源刪除、權限撤回、
  lockscreen／敏感視窗、cloud 限制與過期情境都測。設定模式不自動擴大所有工具權限。
- 回退：停 observer／清可丟棄 context cache；不刪 durable user memory。無觀察仍可正常聊天。

### CP-P06：全身桌面生活

- Claude 將 V04 步態接 root 位移、朝向、工作區、安全區、命中與拖曳；多螢幕／DPI 分平台驗。
- 驗收：走→停→坐→起身→被叫住→恢復連貫；腳步與位移一致、不出畫面、不搶輸入焦點、
  不攔住別的程式；拖曳、鎖屏、全螢幕、螢幕移除可安全收尾。
- 回退：停止漫遊回可見安全點，切回舊可用角色；不自動改系統桌面設定。

### CP-I01：整體體驗驗收

- 固定情境：專心工作→SIRO 自選活動→研究可查→叫她回答→停止／刷新→不復活→繼續新對話。
- Codex 驗視覺，Claude 驗 journal／工具／音訊／程序，使用者驗自然與打擾；三者證據各自標明。
- 套件須對應同一 source／asset／config 摘要（不含 secret），不能混合不同版通過報告。
- 驗收：TASKS 各項＋既有相鄰回歸、owner 實機、已知失敗重測；任何未驗平台保留明示，
  不因單一 Linux 可用宣稱 Windows／WSLg／跨機也通過。
- 回退：I02 演練前只在隔離／owner 試用，未獲部署授權不碰另一台。

### CP-I02：發布與回退

- Claude 準備版本化程式／資產／相容開關，檢查停止／drain、備份還原與新舊 schema 相容。
- 執行一次隔離回退→重新套用，資料不丟；使用者授權後才正式部署，更新共享 STATUS／roadmap。
- 驗收：可重現 release receipt，含測試、資產 hash、schema／migration、未驗限制、停止與回退步驟。
  只有實際演練的層級標 PASS，不能把 source revert 等同正式部署回退。

### CP-O01：選配程序網路監測

- 先列第一版工具／browser 覆蓋盲區，再評估各平台可用的程序歸屬／流量觀測能力及必要權限。
- 驗收：測直接 subprocess 外送是否可歸屬；無能力明示 unsupported，不默默提高權限。
- 不解密 TLS 或抓全機封包作預設。此卡可延期，但不能因此將 adapter log 稱為完整封包稽核。

## 驗證入口（實作時先確認當版存在）

相關既有 baseline：`tests/contract/test_body_adapter.py`、`test_body_assets.py`；
`tests/test_proactivity.py`；`tests/integration/test_gateway_terminal_fence.py`、
`test_body_failure_isolation.py`、`test_agent_batches.py`、`test_agent_runs.py`、
`test_browser_sessions.py`、`test_memory_organization.py`、`test_memory_ingress.py`、
`test_frontend_reflow.py` 與 `test_desktop*.py`。
按影響選適當 unit／contract／integration／regression，新增最小必要動態失敗案例。
檢查 Ruff／mypy／JS、diff、secret／資產來源；全套 check 與平台實測另記。
此列表不是宣稱本輪已執行，不固定挪用歷史通過數字。
