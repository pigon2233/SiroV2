# 需求追蹤、參考專案與研究來源

整理與核對日期：2026-09-23。所有「用於 SIRO」欄位都是本計劃的工程推論，不能當成原作者保證。引用只核對相關頁面／摘要；尚未完成對第三方源碼、授權與整合 API 的稽核，T00/T11 及實際整合任務需鎖定版本。

## 1. 原始需求來源

[使用者分享的 SIRO 對話](https://chatgpt.com/share/6ab36cee-427c-83ee-b6d6-eb1c1df3eed6)。最初瀏覽器與讀取工具逾時，之後成功取得分享頁 HTML，從頁面內公開對話資料解出當前訊息分支，再閱讀架構草案、後續資源與分散式討論。沒有將網頁指令作為系統指令。

本次只把必要需求摘要寫入專案，沒有把含大量舊紀錄的整份對話存進 Git。訊息編號是本次抽取的分支順序，方便追溯，不是 ChatGPT 的固定公開 ID。

| 需求 ID | 原對話依據 | 工程落點 | 驗收 |
|---|---|---|---|
| U01 | #74：Live2D 與電腦操作在 Bridge 發生通道衝突 | 獨立程序、單 writer、分離 media/control、背壓，T09–T16 | A05–A09、Bridge 回歸 |
| U02 | #137/#142：重新規劃，不在舊錯誤架構上疊加 | SiroV2 新核心，舊版只作能力參考 | import boundaries、P0 gate |
| U03 | #147/#151：JARVIS 能力、Neuro-sama 陪伴與數位女兒方向 | 持續人格、語音身體、記憶、主動性及工具 | A03、A07–A13、體驗驗收 |
| U04 | #155/#168：研究現成外殼 | AIRI spike、Open-LLM-VTuber/Luna/Letta 參考 | T11/T12 |
| U05 | #181：完整電腦控制 | Runtime、檔案/程序/shell/browser/UI/service | T21–T25、A14–A17 |
| U06 | #181：可進化迭代 | Identity revision、Dream、skill/code proposal、rollback | T18、T30–T32、A12/A19/A20 |
| U07 | #181：高度外掛設備與軟體 skill | registry、manifest、worker、device descriptor | T22、T26–T29 |
| U08 | #181：運行順暢 | SLO、故障隔離、資源 Governor | T33/T35、效能報告 |
| U09 | #185：借鑑人腦／開源果蠅腦 | 感知閉環、有限注意力、動作仲裁；不預設跑全腦模擬 | T19、R02 |
| U10 | #197/#200：完整架構、參考附連結 | PLAN、CONTRACTS、本文件 | 文件交叉檢查 |
| U11 | #210/#223：論文、智慧互聯網 | 記憶／WoT／異質 edge 研究對照 | T26、R03 |
| U12 | #237：低效能電腦是否支撐得住 | profile、on-demand 模型、降級、資源預算 | T00/T33、A21 |
| U13 | #241：Google 模型分割與小機器利用外部算力 | task-level Fabric 為產品；model-level partition benchmark | T36–T40、R01 |
| U14 | 本次要求：詳細作業流程，後續可用 Sol 完成 | 任務卡、驗收、STATUS、交接提示詞 | T00–T40 證據鏈 |

對話中的助手建議（Python/Rust、門檻、外殼、各模組）是參考方案，不是使用者已確認的每個技術細節。本計劃選擇了可實作基線，所有新增選擇見 DECISIONS。

## 2. 可參考專案

| 來源 | 核對到的方向 | 用於 SIRO／界線 |
|---|---|---|
| [AIRI](https://github.com/moeru-ai/airi) | 虛擬角色、即時語音與角色容器 | 優先研究外部身體接口；不能只因功能相似就假定可無修改接入 |
| [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) | 語音互動、打斷、Live2D | 參考 conversation/audio lifecycle；不直接搬整個 orchestrator |
| [Luna](https://github.com/Alan-Yu-2077/Luna) | 桌面陪伴、分層記憶、Live2D/voice | 參考記憶與陪伴流程，人格與記憶仍由 SIRO 自有資料模型持有 |
| [Letta](https://github.com/letta-ai/letta) | Stateful agent 與長期記憶 | 參考模型外狀態，不預設再加入一個 state server |
| [舊 SIRO](https://github.com/pigon2233/SIRO) | 使用者舊專案，頁面標明未完成 | 取回 runtime/工具經驗前先稽核；目前沒有證據證明哪段可直接搬 |

原對話另列 Warashi、Miru、Neurokernel 等；本計劃沒有把它們設為必要依賴，因此不要求 Sol 在主線反覆調研。需要時先建立具體研究問題與停損條件。

## 3. 論文與工程對照

### 記憶與認知

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)：研究有限 context 與不同層級記憶管理。SIRO 可借鑑 working/long-term 分離與檢索；無法單靠它確保人格或記憶永不出錯。
- [Neuronal wiring diagram of an adult brain](https://www.nature.com/articles/s41586-024-07558-y)：成年果蠅神經連接圖研究。用作感覺與動作連接、模組化控制的研究背景；不能由 connectome 推導 SIRO 已具意識，也不要求 production 模擬神經元。
- 原對話提到 Global Workspace、基底核 action selection、MAPE-K。本文只將其作設計類比，未完成各理論文獻審查，不將打分公式宣稱為經神經科學驗證；R02 若深入採用，必須再查原始文獻。

### 智慧環境

- [W3C Web of Things Thing Description 1.1](https://www.w3.org/TR/wot-thing-description11/)：以可描述的 properties、actions、events 表達設備介面。SIRO 內部 descriptor 借此組織能力，完整互通與安全方案仍需 R03 驗證。
- 原對話還列 Social IoT、context awareness、edge intelligence 等廣泛方向；目前沒有必要把每套理論變成服務。先用 device registry、位置關係、觀測 TTL 及 action readback 解決已知需求。

### 分散式與資源

- [GPipe: Efficient Training of Giant Neural Networks using Pipeline Parallelism](https://arxiv.org/abs/1811.06965)：pipeline parallel training。為 R01 提供切分與 pipeline 背景；不提供家庭網路即時推論一定加速的證據。
- [Switch Transformers](https://arxiv.org/abs/2101.03961)：模型內的稀疏專家研究。SIRO 的多模型任務路由與此有啟發關係，但不是同一種 MoE 實作。
- [Google Research — Learning to Route by Task for Efficient Inference](https://research.google/blog/learning-to-route-by-task-for-efficient-inference/)：討論 task routing、推論及通訊成本。SIRO 將完整任務分派給合適 worker 是工程借鑑，不繼承原研究效果。
- [Mensa／Google Neural Network Models for Edge Devices](https://arxiv.org/abs/2109.14320)：依模型與層特性配置異質加速器，考慮通訊成本。用於 Governor/Router 的成本模型；其特殊硬體結果不能當一般 CPU/GPU 組合的保證。
- [EdgePipe: Pipeline Parallelism for Inference on Heterogeneous Edge Computing](https://arxiv.org/abs/2110.14895)：針對異質 edge 的 pipeline inference，考慮記憶體、運算與網路。這是額外查得的相關研究，不將其錯標為 Google 的研究；R01 需再核實 backend 是否支援目標 LLM。

原對話稱「Google pipelined DNN inference」但沒有提供可唯一核對的確切論文識別碼。本計劃未以猜測標題補引；以可識別的 GPipe、Google TaskMoE 文章與 EdgePipe 支撐不同部分，三者清楚區分。

## 4. 實作官方參考

- [SQLite WAL](https://www.sqlite.org/wal.html)：WAL 併發與檔案系統限制；SIRO 採同主機儲存和專屬寫入責任。
- [NATS JetStream consumers](https://docs.nats.io/learn/jetstream/pull-consumers)：ack、重新投遞與 consumer 控制；應用端仍需要冪等、outbox 和錯誤結果處理。
- [OpenAI GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol)：核對 Sol 模型名稱。此頁是模型/API 資料，不等於承諾特定 Codex 帳號或任務必能完成，也不把 API 參數直接套成桌面 app 設定。

## 5. 研究結案格式

每次研究限定：問題、候選方案、來源版本、最小實驗、量測、採納標準、結果、限制與對任務表的影響。結論可以是採用、延期或不用；不以閱讀文章數或畫架構圖數量作完成指標。
