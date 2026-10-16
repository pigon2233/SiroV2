# SIRO 桌寵、主動陪伴與安全技能成長規劃

## 2026-10-15 更新：介面重設計加入未完成

續作結果：T10-UI-01已完成首個網頁切片的局部驗收（九個獨立工作畫面、333前端PASS、三次真main／Rust／SQLite與24 CUA檢查），**整體PARTIAL**。[實際證據](../evidence/T10-UI-01-2026-10-15/REPORT.md)。下列「本輪只有研究」是前一輪規劃快照，不能再當網頁尚未實作；真Live2D切頁、桌面宿主、全身與動作仍保持未完成。

新增 **T10-UI-01 — TODO / Planned Only**，見 [INTERFACE_REDESIGN_PLAN](INTERFACE_REDESIGN_PLAN.md)。使用者要求不同目的不要同畫面：對話、任務、記憶、能力、設定有獨立導覽與工作內容；日常角色只保留小氣泡和必要互動，詳細操作另開專頁。frontend-design／Hallmark 指導設計；VPet 僅參考桌面角色、活動與互動形式，不直接採用其 Windows/WPF／PNG 動畫本體或角色素材。

本文件既有「桌面場景原型／全身與動作製作／自由活動桌寵」仍為未完成交付，直接沿用，不另建桌寵框架。自由走動、真步態、情緒／嘴型一致與單一 owner 的驗收保持；缺少動作由我們製作，固定常駐或站姿平移不算完成。網頁可先改版，桌面宿主及動作包各自驗收，不等待全部自主進化完成。

本輪只有研究與文件；原型、production UI、宿主／素材與體驗測試皆 NOT_RUN。下方 2026-10-07 的進度與缺口為歷史快照；後續 FIX、D57 及 Runtime Intelligence 成果以 STATUS、FIX_REGISTER 和證據為準，不由舊「尚未接入」文字推翻已驗證成果。

最新實作進度（2026-10-07）：使用者已授權依三份文件開始施工。**FIX-003、FIX-004 DONE / VERIFIED**，見 [003報告](../evidence/FIX-003-2026-10-07/REPORT.md)、[004報告](../evidence/FIX-004-2026-10-07/REPORT.md)；004含固定源碼真瀏覽器306.581秒與整體554 PASS。下一張FIX-005。其餘切片尚未完成，未部署私人服務；不以文字／換證修復代替桌寵、長文語音或自主性驗收。

規劃原稿日期：2026-10-07（Asia/Taipei）。以下原稿的「本輪／只規劃」描述規劃當時，不代表撤銷後續實作授權。

本輪依使用者「只規劃就好」整理產品方案；不改 production code、權限、服務或私人資料。另依使用者「檢查最近的對話紀錄」授權，唯讀檢視有界本機對話與音檔 headers；匿名結果見 [CONVERSATION_VOICE_REVIEW](CONVERSATION_VOICE_REVIEW.md)，不匯出私人內容。程式檢視基準為 c1d2d41；本輪沒有執行功能測試。既有 RT-011／013／015 的完成切片保留，不重新延期、不改 RT／T 編號，也不將下列規劃寫成 DONE。

## 產品方向

使用者最新定義：**桌寵是能自主在螢幕上自由活動的角色**，會選擇去處、走來走去、停留、坐下、玩道具與主動互動；單純常駐的透明聊天窗不符合目標。她也能延續交代的事情、提出建議、學會可靠的新流程。缺少的動作與素材由 SIRO 的製作工作負責生成、綁定與驗證，不能把「沒有現成動作」當作交付終點。

桌寵、網頁、語音共用同一個 Identity、記憶與 Runtime。維持單一角色的視覺與情緒一致性；目前 Haru 保留為現行可用 renderer，正式自由走動需補足全身資產與步態，不以切換多個未驗角色解決。替換身體資產時仍使用同一 SIRO，逐一驗證新包的表情／語音／活動映射，不默默換人格或丟失情緒。

「有想法」以可觀察行為定義：能根據有來源的經歷形成建議、說明理由、保留未完成目標、接受更正，並選擇合適時機行動。不能用隨機動畫或無目的模型呼叫冒充正在思考，也不能將推測寫成已發生的共同經歷。

安全目標是限制錯誤影響、能停止、能回退；不能承諾生成的程式永遠正確。一般新功能走技能或 adapter，只有真的需要新增核心契約時才進受控版本修改。

## 三項最新體驗補充

| 使用者要的成果 | 施工定義與實證門檻 |
|---|---|
| 自由活動桌寵，缺動作由我們做 | 能自己選活動、真正走到別處、玩耍／休息、可被打斷；由我們補角色圖像、分層、全身 rig 與動作包。固定視窗或站姿平移只算原型 |
| 對話自然、理解更正與自己的狀態 | 已檢查有界近期紀錄：句中截斷與自身故障情境缺失需局部修復。用合成口語／代詞／更正／故障追問驗承接，避免一般客服清單與反覆索取已有資訊；保留真實未知，不捏造記憶或修復結果 |
| 語音生成快、長文講得完 | 使用者已澄清是等待及長文不完整。第一切片重用 segmenter、單 worker、有界預取，逐段播到全文末句；一般短答與完整朗讀清楚區別。再評估 final-answer 完整句提早生成；取消與新 turn 清掉全部待播，既有聲線保留 |

完整證據、未知項與驗收見 [CONVERSATION_VOICE_REVIEW](CONVERSATION_VOICE_REVIEW.md)。文字 output budget 與語音 codec limit 是兩個限制；不能用「加大一個上限」處理兩者。頁面 300 秒 token 未續期的局部整合缺口也納入，不能把 Gateway 401 與上游 provider HTTPStatusError 混為同一根因。修復任務為 FIX-003／004／005／006，皆只定義、尚未執行；搜尋 FIX-002 保留。

## 已有能力與實際缺口

| 範圍 | 可重用的實作證據 | 進入產品前仍需完成 |
|---|---|---|
| Live2D 與情緒 | [Web body](../../src/siro/adapters/body/web.py)、[renderer preparation](../../scripts/repair_companion_renderer.py)；單一 renderer owner、最新情緒恢復 | 自由漫遊的桌面場景、全身步態／活動資產、輸入區域、焦點與平台驗證；網頁 iframe 與桌寵不能搶 owner |
| 主動陪伴 | [ProactivityRules](../../src/siro/core/proactivity.py) 有 quiet／busy／speaking／冷卻／每日上限 | 尚未接產品事件與排程 caller；需持久去重與明確任務來源 |
| 閒置記憶整理 | [MemoryOrganizer](../../src/siro/services/agent/organization.py) 已接 lifespan，100 個來源／5 秒、前景取消、可丟棄 view | 保留既有 scope；不是自主寫 facts、對外操作或通用代理迴圈 |
| 擴充技能 | [manifest](../../src/siro/core/skills.py)、[registry](../../src/siro/persistence/skills.py)、[worker](../../src/siro/adapters/skill_worker.py)；預設停用、schema、bubblewrap、資源上限 | 尚未接 Gateway 的 ToolCatalog 與產品安裝／撤銷入口；完整性目前只 hash manifest／schemas，未涵蓋執行碼與依賴 |
| 經驗轉技能 | [ProceduralCandidateGenerator](../../src/siro/core/procedural.py) 從重複可信成功 traces 產生 review-only 候選 | 尚無實際 run → 候選 → 獨立驗證 → 啟用閉環；成功紀錄不保證泛化正確 |
| 修改驗證 | [PatchVerifier](../../src/siro/core/evolution.py) 複製目錄與執行檢查 | 同帳號 subprocess 不是 OS sandbox；會繼承環境，copy 排除清單未排除 .env.local，protected paths 只有兩個檔案。不能直接接自主修改 |
| 發布回退 | [ReleaseManager](../../src/siro/core/releases.py)、[CLI](../../src/siro/cli.py) 有 staging、healthcheck、指標與備份 | launcher 尚未消費 active.json；HMAC 未覆蓋 schema 相容欄位；rollback 在指定 DB 時會回復舊備份，可能丟失之後的記憶與 ledger |
| 電腦能力 | [Gateway composition](../../src/siro/services/presentation/gateway.py) 的 computer.execute 可執行一般帳號 argv | 同帳號可寫目標沒有核心保護邊界；full 自動授權不能原樣繼承給自主工作或候選驗證 |

[SKILL_DEVELOPMENT](../SKILL_DEVELOPMENT.md) 仍描述沒有 kernel-level isolation，但 worker 現有 bubblewrap 路徑；需校正文案並驗證實際安裝環境，不能據舊文案重造 worker，也不能據 helper 存在宣稱整個產品已安全。

## 桌寵體驗

日常主體是一位在螢幕場景中生活的角色。她可以自主決定散步、停在選定位置、坐下休息、玩自己的小道具或靠近互動區，不必等每次聊天指令才動。點角色展開對話；可拖曳、調整大小、設定活動區域、暫藏、靜音、專注與停止活動。記憶、技能、權限和詳細活動從控制頁進入。退出桌寵與停止 SIRO 服務的意義必須分開。

| 使用情境 | 使用者應看到的結果 |
|---|---|
| 沒有交談 | 自選散步、看向互動區、玩桌寵道具或休息；有可見步態與活動銜接，不搶輸入焦點 |
| 選擇新位置 | 起步→走到目標→停步／轉向→到達後活動，速度與腳步同步；不能只平移站姿 |
| 正在專注工作 | 遵守指定活動區與 Focus；可安靜休息，不擋正在輸入的區域，不假裝執行工具 |
| 有值得提醒的未完成事項 | 一則有理由的小提示；可稍後、取消或停止此類提醒 |
| 正在做已交代的事 | 真實任務狀態、目前步驟與停止入口；成功只在結果回讀後顯示 |
| 想到可改善的流程 | 「這個步驟我們做過幾次，我想整理成技能」；可看來源、驗證結果與權限差異 |
| 使用者開始聊天 | 停止背景語音，優先處理前景；背景工作取消或在安全 checkpoint 暫停 |
| 角色視窗崩潰／重開 | 對話與記憶仍可用；恢復最新情緒，不重播過期語音、動作或工具 |

外殼只管視窗、顯示、輸入與生命週期，不持有第二套 Core、SQLite writer、人格或授權邏輯。第一版指定桌寵為唯一 body／音訊 owner，控制頁不再同時掛 renderer；切回網頁時明確交接。現有 bridge 收到 renderer replaced 後會停止重連，因此交接必須重新啟動／訂閱指定 renderer，不能假定關閉桌寵後舊 iframe 會自動復活。沿用 loopback HTTP origin、session 與 WS 驗證，不能為 file/null origin 放寬權限；驗收超過目前 300 秒 token TTL 的安全重新認證／bootstrap，不改為永久 token。

第一個實測目標沿用 [開發環境盤點](../ENVIRONMENT.md) 的 GNOME／Wayland，實作時重新確認當前平台。先用同一 Haru renderer 做短範圍外殼選型驗證，再鎖定 toolkit；Electron 可列為重用 Web renderer 的候選，尚未選定或新增依賴。其官方文件明示 Wayland 自動定位、移動及焦點限制；滑鼠穿透也必須按鎖定版本實測，不能套用 X11 的成功結論。[Electron BrowserWindow](https://www.electronjs.org/docs/latest/api/browser-window/)

選型必測：native window → WebView → HTML → WebGL 全透明鏈、角色命中區與空白穿透、拖曳和輸入焦點、多螢幕／DPI、全螢幕／鎖屏、托盤或等價入口、單一 owner、故障後重連。現有 renderer 的 HTML 背景並不透明，直接包現有頁面不是完成桌寵。**自由走動是正式驗收必要條件；固定停靠／只能拖曳僅可標示為降級，不能用它宣告桌寵完成。**

優先驗證「覆蓋指定螢幕 output 的透明表面，角色在表面內移動」，以避免每幀要求 compositor 移動 native window；這仍是待驗假設，需證明表面位置、原生 input region、空白穿透、角色可點、不搶焦點與全螢幕政策。另比較移動小型 native window；若兩者在目前 GNOME／Wayland 都不成立，再評估窄幅 compositor 整合或明示的相容模式，不能默默改桌面 session。只有整個透明窗穿透、角色也點不到，或必須攔截全螢幕輸入，都不算通過。

若採 Electron，renderer 關閉 Node integration，保留 context isolation／sandbox；native bridge 僅開必要視窗操作，限制導航與 IPC sender，外部網頁另走既有受限 browser 工具，不在有 native bridge 的角色視窗內開。[Electron Security](https://www.electronjs.org/docs/latest/tutorial/security/)

## 自選活動與螢幕場景

「自由」在已驗證的活動、位置與互動範圍內成立；她可自己選活動與去處，使用者可限制區域、暫停或叫她回來。螢幕上的玩耍與移動不等於可自行點擊其他程式、拖走檔案、購物或修改設定；這些仍走既有工具授權。

| 責任 | 最小設計 | 不承擔的責任 |
|---|---|---|
| 活動選擇 | 低頻從散步／看向互動區／玩道具／休息等候選選一項，讀既有情緒投影、Focus、前景與近期活動；有期限、冷卻與取消標識 | 不逐幀叫模型；不生成任意程式或 OS 指令，不自行更改情緒來源 |
| 桌面場景控制 | 單一 presentation owner 管理可用螢幕幾何、活動區、路徑、步速、朝向、角色碰撞／命中區與活動切換 | 不另造人格、Memory DB writer、業務 scheduler 或工具執行權 |
| 動作／繪製 | 將活動映射到版本化資產，執行局部步態、過渡與道具動畫 | 不判斷真實任務是否完成、不替自己授權、不覆蓋 Core affect |

先用有狀態、可重現的規則建立活動連續性；模型只在有價值且有預算的語意選擇參與。一次一個主活動、有限候選，活動保持合理時間，不每幀亂換。桌面微活動不佔用一個 computer.execute job，也不因上一個動作結束就無限創造新的業務目標。

場景先使用螢幕工作區與使用者設定的安全區域，可形成虛擬地面／休息點與桌寵自己的道具。若要坐在真實其他程式的視窗邊框，須另外驗證可用的 window-geometry adapter 與授權；漫遊本身不依賴讀螢幕內容。游標互動只用平台允許的本機指標事件、不保存軌跡；不可取得時不宣稱已能全域追蹤游標。

拖曳、使用者說話、Focus、停止與螢幕移除都可打斷活動；路徑重新計算有上限，失敗停在可見安全區，不在邊界抖動或走出畫面後失聯。重連／重啟恢復最新情緒與安全待機，不重播舊 walk／jump callback；每個活動帶 generation／epoch 以拒絕過期完成通知。

情緒、身體與嘴型有各自唯一控制來源：Core affect 擁有表情，場景控制擁有 root position／身體活動，音訊路徑擁有說話／嘴型；各參數優先序與 channel mask 要有契約測試。停止走路不清掉表情或取消另一條有效語音。現有 sample 的 stopSiroMotion 會連 expression manager 一起停止，不能直接拿來當日後的 locomotion cancel。

沿用可丟棄的 BodyAdapter 邊界；若需要新的活動意圖，實作前只補窄幅 versioned presentation 契約與兼容測試。Core 不知道步行座標、每根骨骼或每張素材；增加一般動作是加資產／映射，不在 Core 加一個個 action if 分支。

## 缺少動作的生成與製作

**責任：動作設計、圖像／姿勢素材生成、參數動畫製作、資產打包與驗證均列為我們的交付工作。**本輪只規劃，未生成圖像或動作；不要求使用者先找齊素材才能開始。仍須如實區分「生成圖片」「可編輯全身模型」「可用 Live2D 步態」三種產物。

本機 Haru 的文字資產位於 models/live2d-sdk-5-r.5/CubismSdkForWeb-5-r.5/Samples/Resources/Haru。Haru.cdi3.json 的 42 個參數涵蓋臉／眼／嘴／上身／手臂／頭髮，未提供腿／膝／腳步參數；27 份 motion 中 model3 只掛 2 個 Idle、4 個 TapBody，未有已驗證的 walk／play 映射。本機該目錄沒有 PSD／CMO3／CAN3。Loop=true 與動作檔名不能證明存在步態；本輪未檢視 binary／texture，因此不據 metadata 推論畫面裁切範圍。

現有 rig 可先擴充它已能表達的注視、點頭、呼吸與手臂動畫；真的增加腿部／全身步態，要有可編輯全身素材與對應變形器。官方資料說明 CMO3／CAN3 與 MOC3／motion3.json 的製作／輸出關係，motion 播放操控既有模型參數；圖片生成不能憑空替 runtime 模型長出腿部參數。[Live2D 輸出流程](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)、[Motion](https://docs.live2d.com/en/cubism-sdk-manual/motion/)

第一套製作目標為單一、可編輯的全身 SIRO，保持角色設計一致；原創設計列為正式產品候選，避免為缺動作就混搭不同角色。若沿用／改作 Haru，先核對適用來源與授權；官方另提供可編輯來源，無需把現有 MOC3 逆向成工程。新資產未驗收前保留目前可用 renderer，不自動切換。[Haru 官方資料](https://www.live2d.com/en/learn/sample/haru/)、[Sample terms](https://www.live2d.com/eula/live2d-sample-model-terms_en.html)

| 製作階段 | 我們要交付的東西 | 完成條件 |
|---|---|---|
| 角色與動作設計 | 全身設計、左右朝向、比例／服裝／髮型一致規格、姿勢與表情參考 | 同一角色在站立、走路與坐下可辨識，不靠換角色完成不同動作 |
| 素材生成與整理 | 透明圖像、可編輯分層、關節遮擋補圖、道具與素材來源紀錄 | 臉／身體／四肢／服裝分層正確；生成的平面圖不冒充 rig-ready PSD |
| 全身綁定 | ArtMesh、變形器、左右腿／膝／腳／骨盆／重心與身體擺動，保留工程來源 | 參數範圍有效、轉向與關節不破圖、能匯出供目前 renderer 使用的模型 |
| 動作生成 | 已驗證參數的 curves／motion3.json、過渡、循環與參數 channel mask | 起步／停步／轉向／坐下可銜接，步幅與 root 位移同步、腳不滑地 |
| 實際合成與發布 | 模型／動作／表情／道具／映射的固定版本包，畫面證據與回退版本 | 不覆蓋情緒／嘴型、可取消、來源與相容性清楚，失敗只撤資產包 |

第一批活動資產：站立／注視；起步／左走／右走／停步；轉向；坐下／坐著／起身；揮手／被提起反應；以及一條完整的「看向道具→碰道具／玩耍→收尾」活動。後續加入睡覺／醒來、好奇探頭、伸懶腰、跳躍等；新動作仍沿用相同控制介面與參數規則。任務思考／工作姿態只能表示真實對應狀態，不以動畫聲稱正在執行工具。

製作工具也有實際條件：官方 Cubism Editor 的支援環境為 Windows／macOS，Linux 上 Web renderer 成功不代表已具備 rig 編輯／輸出環境。需在製作切片先打通可操作的工程／匯出工具鏈；不能承諾僅呼叫影像生成就自動得到可用 MOC3。[官方 Editor 系統需求](https://www.live2d.com/cubism/download/spec/)、[ArtMesh](https://docs.live2d.com/en/cubism-editor-manual/concept-of-artmesh/)

資產包只含允許格式的模型／圖片／JSON 資料，具完整 digest、角色／renderer 相容範圍、活動與情緒映射、參數 channel mask、資源限制及來源紀錄；不得夾帶任意 JS／native code。先離線驗證，再於安全待機原子切換。缺動作回到有標記的安全待機，不自動下載／執行陌生程式；新動作走同一候選／驗證／試用流程，失敗不回復舊記憶。

## 主動性：從延續交代的事情開始

主動性分成上述「桌面自選活動」與「會處理真實任務的背景工作」。前者讓角色自由走動與生活，不要求使用者先交代待辦；後者的第一個完整用途選 **使用者明確交代的未完成任務追蹤**，搭配已存在的本機記憶整理，再逐步加入已訂閱主題的研究草稿、工作流程建議。兩者共用情緒與使用者模式，但不共用逐幀排程，也不需要新的認知架構。

- 任務必須有明確 owner、原始要求、來源、下一步與狀態；有指定期限才設提醒時間。AgentRun 是執行紀錄，不能把所有 failed／unknown run 自動當成應重做的待辦。
- 事件來自明確任務、更正／刪除、可信執行結果及使用者訂閱；閒置可觸發有界檢查。桌寵啟動不自動授權讀螢幕、相機或整顆硬碟。
- 沿用既有 ProactivityRules、有界執行／取消、governor 與 journal 能力，在 service composition 接可信 caller；不另造第二個 scheduler、Memory owner 或工具 dispatcher。
- 有候選才判定是否需要模型；背景整理、到期檢查與待機動畫不每幀呼叫模型。期限、工具步數、雲端費用、來源數量和候選保留量都有上限，無配置不能無限跑。
- 第一版同時最多一個背景工作，使用者輸入／Focus／停止具有優先權；CPU/GPU 壓力或預算耗盡時暫停。這是規劃初值，未改設定，未聲稱已量測。
- 背景單次工作先沿用 PLAN 的最多 8 個工具步驟／120 秒，額外限制候選佇列最多 8 件、相同 task revision 合併；到期留下 checkpoint，不自行延長或無限重新排入。這些是待驗證初值；正式每日雲端預算未配置時，不開始背景雲端呼叫，明確使用者對話仍按原授權處理。
- 保留現有安靜時間、社交冷卻與每日上限。產品設定分開「安靜做事」與「主動說話」，讓使用者一次設定允許的類型／範圍／期限，不每個低風險步驟重問。
- 提醒以 task ID＋revision＋提醒窗口持久去重；重啟、事件重送、來源更正／刪除後不能重複提醒或引用失效資料。有副作用的 unknown 結果先回讀，不自動重送。
- 每次主動行為可查看觸發理由；推測與建議不成為已確認 facts。使用者可更正目標、停用某類主動性或一鍵停止全部背景工作。

在上述硬邊界內，模型可以選擇哪件事值得做、形成自己的建議，也可以選擇等待。她不能因「情緒」「無聊」或網頁指令擴大權限。

## 自主程度與電腦存取

| 層級 | 可做的事 | 必要界限 |
|---|---|---|
| 陪伴／桌面活動 | 同一套有來源的情緒狀態、對話、自選走動／玩耍／休息、使用者要求的操作 | 活動在使用者允許的螢幕區域；真正 OS 操作另經授權，共用既有 Core |
| 主動整理／提議 | 本機既有來源整理、任務提醒、提出流程／技能草稿 | 來源可追溯、預算、可取消、可更正；不暗中執行提案 |
| 已授權背景工作 | 指定主題研究、指定資料夾索引、指定產物草稿 | 固定資源／目的地／期限；私人資料外送另受 privacy gate；不能繼承 general full 模式 |
| 有界技能成長 | 在隔離區產生與驗證候選，依既有策略啟用低風險版本 | 通過獨立驗證、完整包 hash、同權限、可撤銷、有限試用；新增權限或依賴須走 owner control path |
| 核心更新 | 提出 Core／權限／資料 migration／發布機制修改 | 維持受控工程與發布流程；不允許自主候選自行簽署、改驗證器或直接部署 |

「能操作整台電腦」與「能修改自己的信任邊界」必須在 OS 層分開。使用者交代的合法一般檔案／程式操作保留；受保護安裝、policy、憑證、資料庫與 activation records 由不同權限持有，工具程序拿不到直接寫入能力。正常資料更新經受控 service API；候選只拿必要的合成／脫敏輸入，不掛私人 DB。

不能只封鎖 sudo／shell：Python、編輯器、套件管理器、symlink 或主機控制 socket 也可能繞過文字限制。需驗證工具無法取得 Gateway／updater 憑證、主機任意執行入口或受保護掛載；禁止把 privileged broker 做成可任意 exec 的後門。可用性由明確能力 grant 提供，權限由 Runtime 執行。

## 安全進化流程

先支援從成功經驗學會 **既有工具的流程**；只有流程無法表達時才產生新的執行碼。記憶／偏好學習、流程學習、技能程式與 Core 發布分開處理，不要求每次成長都改程式，也不把模型權重訓練列為此切片依賴。

1. **發現價值**：由多次可信成功 traces 或使用者要求提出候選，保留來源、預期收益、失敗案例；候選不等於已啟用技能。
2. **隔離產生**：只寫專用候選區；無 production 寫入、無 secret、無私人 DB、預設無網路。保留完整版本與依賴鎖定；不升級正在使用的 .venv。
3. **獨立驗證**：可信 verifier 與測試基線在候選可寫區之外；驗證 schema、相容性、權限差異、完整執行碼／依賴 digest、輸出與資源限制。候選測試只能補充，不能取代固定驗收。
4. **無副作用演練**：用合成資料、recorded fixtures 或 shadow 結果比對；不因 replay 再做真實操作。注入失敗、超時、惡意內容與取消；來源失效時取消待啟用候選。
5. **有限試用**：同權限、可停止、可逆的技能可依使用者已設定政策做有界試用；先限定任務／次數／期限。涉及外送、破壞或不確定外部效果的技能不得靠測試全綠自動放行。
6. **可信啟用**：獨立 activator 固定 verified artifact、版本與許可；切換只影響新 run。模型與候選不能修改 registry、簽署金鑰、允許清單或驗證結果。
7. **觀察與撤回**：可信 supervisor 依健康、錯誤、取消和預算指標停用／隔離失敗版本，恢復已知良好技能；在產品中說明變更與結果。

**程式回退預設保留最新資料**：不因技能／程式版本回退就把記憶、任務與 action ledger 覆蓋回舊 DB。以向後相容的增量資料變更優先；舊版本讀不了目前資料時進 safe mode／停止切換並明報，不能自動丟資料。真正資料還原是獨立 maintenance 操作。回滾程式不會撤銷已發生的寄信、刪檔或設備動作，也不能重播它們。

OpenClaw 可借鏡的是有 owner 的 heartbeat、技能提案／版本與受控套用流程；其 Skill Workshop 明確區分 pending proposal 與 live skill。這支持 SIRO 的候選／啟用分離，不能推出「模型可安全任意改自己」。[OpenClaw Heartbeat](https://docs.openclaw.ai/gateway/heartbeat)、[Skill Workshop](https://docs.openclaw.ai/tools/skill-workshop)

OpenClaw 也明示 skills allowlist 不是 host shell 授權邊界，sandbox 不能保證完美隔離；其更新文件區分程式回退與資料相容性。SIRO 應驗證自己的 OS／Runtime／資料邊界，不整套移植、不把更多 abstraction 當成進化成果。[Skills](https://docs.openclaw.ai/tools/skills)、[Sandboxing](https://docs.openclaw.ai/gateway/sandboxing)、[Updating](https://docs.openclaw.ai/install/updating)

## 擴充功能的穩定邊界

| 新功能種類 | 接入位置 | 正常變更範圍 |
|---|---|---|
| 既有工具的新流程 | procedural 候選／經驗配方 | 流程、參數、來源與測試；不改 Core |
| 新的運算／整理技能 | SkillManifest → registry → 隔離 worker | 獨立版本包、schema、fixtures、產品 enable／disable |
| 新網站 API／設備／OS 能力 | 對應 adapter／driver＋既有 capability catalog | adapter 與 composition 接線；授權與取消經既有 Runtime |
| 新桌面活動／動作／外觀 | presentation scene／body adapter＋固定資產包 | 活動與參數映射、renderer、模型／動作／道具；不另造記憶或人格、不逐動作改 Core |
| 現有契約表達不了的能力 | 小範圍 versioned contract 修正 | 先證明缺口、ADR、兼容測試與 migration；再修改必要核心邊界 |

最小技能接法：composition 將已啟用的固定技能版本轉成 namespaced ToolDescriptor；沿用 ToolOrchestrator 的授權、journal、取消，再交 SkillDispatcher／WorkerSupervisor。安裝、驗證、授權與啟用走 owner control path，不能成為任意模型可呼叫的「自我授權工具」。Core 不 import 第三方 Python；技能不直連 Core DB；未知／不相容版本拒絕載入，錯誤只隔離該技能。

先接一個唯讀整理技能，驗證安裝→啟用→呼叫→取消→停用→移除→回退整條流程。完整包 digest、不可覆寫版本與依賴鎖定是自生成程式啟用前的門檻；先沿用 manifest v1，確有新能力需求時再版本化。現有 network=denied 不因插件要求就轉為 unrestricted；有網路需求時先定受限 broker 契約與資料外送 gate。

不新增平行的 plugin manager、通用事件總線或另一套工具協定。一般擴充應不修改 Core；新增受信任 capability 可能需要有限 composition 接線，不能承諾所有未來需求零核心變更。

## 分階段交付與回退

下表是施工依賴，不是 RT 排名或新編號；每個階段都需可見產物，不以 class／helper 存在當完成。

| 切片 | 可交付成果 | 驗收門檻 | 回退與依賴 |
|---|---|---|---|
| 現有體驗缺陷 | 搜尋、文字完整性、session 續期、分段朗讀與自身故障情境的最小修復卡 | 正常查詢有來源；不把截斷當完成；跨 TTL 正常互動；語音早播首段且全文完整；理解更正與自身已知／未知 | 按 FIX-002–006 各自 gate；provider／實際尾端問題仍需合成調查，本輪不宣稱已修 |
| 桌面場景原型 | 真平台透明場景、可點角色、場景內 root 移動、聊天與停止／暫藏 | 透明／焦點／穿透、唯一 renderer／音訊 owner、崩潰後對話仍可用；站姿平移只算原型 | 關閉外殼後明確交接回現有網頁；不換 Core／DB，不宣告已完成自由桌寵 |
| 全身與動作製作 | 單一角色可編輯來源、全身 rig、步態／轉向／休息／互動與道具資產包 | 圖像→分層→綁定→匯出工具鏈成立；真步態、循環與過渡、情緒／嘴型不被覆蓋 | 保留現有資產與固定回退包；不因缺現成動作就放棄製作 |
| 自由活動桌寵 | 不需聊天觸發，自選去處、走動、玩道具／休息，隨時可叫回或停止 | 真螢幕完整活動鏈、步速同步、可打斷／拖曳、邊界／DPI／螢幕移除恢復；停靠／平移不算 DONE | 停漫遊或回已驗資產包；情緒、Core／DB 與一般對話保留 |
| 第一個擴充閉環 | 一個唯讀技能可安裝、啟用、使用、停用與回退 | 經既有 catalog／授權／journal／worker，崩潰及取消不傷主程式 | 停用該版本、保留資料；不用先開自主生成 |
| 第一個主動用途 | 延續明確未完成任務；沿用本機記憶整理 | quiet／Focus／前景優先、去重／重啟、更正／刪除、真實狀態、預算 | 關該類主動性，保留原任務；唯讀切片不必等待完整自我更新 |
| 自主技能候選 | 成功經驗→可審查流程／程式候選→隔離驗證 | OS 保護、無 secret／private DB、固定 verifier、完整 artifact hash、無提權通道 | 丟棄候選不影響 production；隔離未通過只停用這條接線 |
| 有界技能成長 | 已授權範圍內試用／啟用與故障隔離 | 有效 activator／supervisor、來源有效、限額試用、代碼回退不回覆舊 DB | quarantine 單一技能，回已知良好版本；信任邊界驗收通過後才接 |
| 受控核心發布 | 真正 launcher／service 消費已驗證版本並可恢復 | 完整 manifest 認證、drain、啟動健康、資料相容、safe mode／部署演練 | 舊程式讀新資料；不相容則停止回退，不自動還原 DB；不授權模型自主改 Core |

桌面場景與全身素材製作可並行；自由活動桌寵要兩者與活動控制都完成才驗收。桌面產品與主動唯讀用途可在各自 owner／取消邊界明確後並行。安全技能成長依賴完整技能閉環和 OS 保護；不是把所有產品成果一起卡到自我更新完成。

## 驗收與保護區

| 邊界 | 必要實證；下列均為待執行驗收 |
|---|---|
| 桌面真體驗 | 無使用者逐次命令也能選活動，走到另一處並玩耍／休息；腳步與位移同步、過渡自然；情緒跨活動／對話／重連保留，停止走路不清表情；無雙重聲音、透明區不擋其他程式，外殼崩潰不丟記憶 |
| 場景與資產 | 拖曳／Focus／停止能打斷，過期 callback 不復活；多螢幕／DPI／拔除輸出回安全可見區；缺資產／破損／不相容只拒該包，不執行包內程式；改一個普通動作不需改 Core |
| 主動性 | 合成任務跨重啟不重複；停止／前景輸入立即阻止新背景 dispatch，受控工作遵循既有取消門檻；source revision／delete 後不引用舊內容 |
| 資源 | 記錄動畫 idle、對話、背景工作的 CPU／GPU／RAM、延遲、喚醒及雲端費用；先量測再定發布門檻，假時鐘不是長時間 soak |
| 權限 | 網頁提示注入無法開新權限；自主 worker 經 Python／symlink／套件管理器／主機 socket 都不能改受保護區或取 secret；local-only 網路阻斷成立 |
| 擴充 | 新普通技能只改自己的包／fixtures；同版本換碼被拒；不相容 manifest、撤銷、超時、子程序、輸出洪水與 crash 被隔離 |
| 演進 | 候選不能改固定測試／啟用權；失敗技能撤回後，新記憶／任務／action ledger 還在，無 effects replay；失去可信 activator 時停止新 promotion |
| 現有產品 | 既有文字、工具 pairing、native context budget、memory privacy／revision、前景取消、Live2D／音訊契約仍有效；追加終止原因／未完成狀態、跨 300 秒換證、對話更正、長文尾句／首音時間／取消；真 provider／真桌面／真聲音與 mock 測試分開記錄 |

RED：Identity 不可變規則、授權／privacy、secret、action ledger、資料 migration、verifier／activator／可信 supervisor。自主候選不可修改；必要人工修復仍可走正常受控流程。

YELLOW：Gateway composition／session lifecycle、model 終止裁決、語音分句／播放 owner、Runtime adapters、browser／computer 能力接入、scheduler owner 與版本契約。只做有 evidence 的局部接線與兼容修改；asset GREEN 不代表音訊／情緒 owner 可任意更換。

GREEN：既有契約內的桌寵外觀、隔離技能包、合成 fixtures、候選草稿與可丟棄投影；仍受資源、來源與權限限制，GREEN 不等於可隨意部署。

## 本輪搜尋故障

使用者提供的工具畫面顯示 Markdown 連結字串，並回報 ScopeViolation；尚未取得 raw arguments，不能將顯示格式直接當成當次根因。已列入 [FIX_REGISTER](FIX_REGISTER.md) 的 FIX-002，先修正已確認的診斷資訊遺失、用合成頁面辨別參數／主頁／轉址／子資源拒絕；必要行為修復依證據另定最小切片。

故障不能以關閉 URL scope 檢查處理，也不能據此把既有 RT-012 所有 acceptance 改成失敗。**BLOCKED_BY_FIX 僅涵蓋自動網路研究 promotion**，須正常網址／來源回讀與失敗處理驗收通過才解除；不阻擋桌寵與本機唯讀任務追蹤交付。本輪未確認 Bing 當次根因、未修復或重試該查詢。

## 本輪產出與未執行事項

產出為本規劃、搜尋及對話／語音修復定義、匿名檢視與文件交接。程式證據為靜態 call-path 檢視；OpenClaw／Electron／Live2D／Qwen 為官方文件研究，不代表 SIRO 已整合或通過新能力。依使用者追加授權唯讀檢查近期對話、服務狀態碼與音檔 headers，未匯出原文／音檔、重播或生成測試音訊。本輪沒有改程式、安裝外殼、生成角色／動作、啟用主動性、更新模型、執行候選、寫私人 DB、重啟服務或執行上述功能驗收。

## 2026-10-16 implementation checkpoint

已實作獨立GJS/GTK3/WebKitGTK4.1 native host、/desktop透明模式、角色點擊聊天／明示拖曳／控制台／最小化／退出、single GtkApplication與desktop body優先權。真本機XWayland相容路徑ready、RGBA alpha、像素input region與sandbox已量測；非原生Wayland或全桌面驗收。framework輸入區域資料不冒充owner實際滑鼠穿透／多螢幕／全螢幕人工驗收。

仍未完成：Haru腿部rig／walk/play/rest套件與自由活動gate，沒有用站姿滑動造假；原創全身／可編輯來源流程保留。首段語音CPUtests完成但kernel更新後NVIDIA module缺件使GPU速度驗收被阻；限流僅有界可取消重試，不增加免費quota。詳 DESKTOP-VOICE-RECOVERY-2026-10-16證據。整體桌寵卡仍PARTIAL，不能因nativewindow存在宣告完整活動系統DONE。
## 2026-10-17 GPU follow-up

使用者完成driver repair後，CUDA blocker已解除；原v1聲線真RTX3050 first24暖未快取7.781／10.109s（舊首段21.648／21.694s）。當前隔離前端三段真實播完及真停止→prefetch worker回收0.517s已驗，正式8000／單native host已恢復。惟cold首播18.789s、段間23.977／14.926s，語音速度體驗仍FAIL，FIX005及整體產品保持PARTIAL；人工聽驗仍待owner回饋，自由活動素材門檻不變。此段更新前次GPU_DRIVER_BLOCKED checkpoint，不將歷史未驗項補記PASS。詳 [真機複驗](../evidence/FIX-005-first-segment-2026-10-17/REPORT.md)。
