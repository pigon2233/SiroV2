# SIRO 實際能力需求研究

> 2026-10-06 後續交付：使用者已明確授權三項實作，有界產品切片已完成。本文的 DEFER 是規劃時狀態；目前狀態與限制見 [PRODUCT_QUICKSTART.md](PRODUCT_QUICKSTART.md) 和 roadmap 最新交付段落。

2026-10-06；範圍：本地產品規格、目前 implementation 與既有 tests 的靜態研究。未寫程式、未跑新測試、未使用私人聊天；不是外部產品比較。接續 [DEFERRED_TASK_PLAN](DEFERRED_TASK_PLAN.md)，三項仍 DEFER。

## 結論

產品規格已支持「閒置時整理已有來源的記憶」作為 RT-015 第一個研究用途，不必再把整個需求探索交給使用者。但規格是產品方向，不等於使用者已啟用背景處理或同意新的 cloud 外送。第一個可驗證範圍應是**整理候選與來源核對**，在更正／刪除傳播成立前，不開啟自動持久寫入或主動通知。

RT-013 暫無已指定的資料夾與實際 caller，繼續 DEFER。RT-011 可先用合成長對話區分「窗口遺失目標」「合法 context 超限」「native shape failure」，不能統稱需要摘要。

## RT-015：需要的使用者能力

依據：PLAN §6.4 已要求 idle Dream、來源、候選→驗證→版本、可取消 checkpoint；EXPERIENCE §3.3 要求更正、刪除及衍生摘要撤銷。這比新增外部提醒或一般背景 agent 更貼近既有 SIRO 範圍。

建議行為：

- 只處理已明確要求記住、來源仍有效的內容；第一輪不掃描所有原始聊天、檔案或工具 output。
- 閒置時找出重複／可能衝突的記憶並提出整理候選；不靜默合併互相矛盾的陳述，不推測人格或關係。
- 保留原記憶與來源；候選可丟棄。第一版不自動增加 committed facts，也不要求每次完成都打擾使用者。
- 使用者開始互動便停止接收背景工作並取消可停止部分，前景不能等待整批整理完成；已提交的原子交易不能宣稱可被取消撤回。
- local-only 資料不能為了摘要直接送 cloud。若沒有可用的本機模型，先做確定性的來源／版本核對或維持 DEFER，不假定現有 cloud route 可用。

這裡的「整理候選」是計畫中的未實作能力，不是已存在的產品按鈕。

### 為什麼不能只接一個 timer

| 實際 code 證據 | 接入前必須回答 |
|---|---|
| ConsolidationScheduler._runs 由 wait/close 清理；schedule 沒有全域 capacity gate | 誰回收每個結果？不同 run_key 洪水會否累積？foreground 到來如何取消？ |
| Consolidator 收到外部提供的 candidates 後逐一 commit | 沒有從現有記憶產候選的正式 caller；scheduler 本身不會整理對話 |
| SQLiteConsolidationRepository.commit_candidate 對 inferred 且來源少於三個才標 candidate，其他可 committed | 三個 event IDs 不等於三份獨立證據；不能直接沿用這個條件把生成內容自動當成已確認記憶 |
| 此 commit 連結 memory_sources 的 event IDs；未建立 memory_derivations 邊 | 有 event provenance 不等於有 parent-memory revision／衍生關係 |
| SQLiteMemoryRepository.delete 沿 memory_derivations 遞迴；correct 更新本身 revision／FTS | 必須實證背景衍生內容與刪除圖相連，並在更正時失效；不能以已有 delete API 宣稱閉環完成 |

以上是接入的已知條件與靜態缺口，不是本輪已重現 production failure。現有 consolidation cancel/resume/crash tests 有價值，但測的是給定 candidates，未證明自動產生候選與更正競態安全。

最小研究實驗：合成六組內容（重複、明確更正、刪除、衝突、local-only、工具偽造指令），在隔離 fixture 只輸出候選清單；每項附 parent memory ID、revision、source IDs 與判定理由。插入 foreground／更正／刪除／重啟事件，驗證過期候選零採用、原記憶零自動覆寫、停機零殘留 task。通過後再評估持久候選接入，先沿用既有機制，不預設需要新表。

尚待決定的產品偏好只有：是否啟用背景整理，以及是否允許將候選自動升格。建議初值為 off、候選不自動升格；本輪不要求使用者先回答才可研究。

## RT-013：受限檔案讀取

產品 PLAN 支持電腦／檔案能力，但目前未指定「只可讀哪個目錄、為何需要讀、從哪個工具呼叫」。不能自行把 repo、家目錄或 .siro-data 當成授權範圍。

值得啟動的具體情境例子是：使用者選定一個筆記／工作目錄，要求 SIRO 搜尋或讀取其中檔案，禁止越出 scope。這只是候選需求，不是目前已授權使用情境。

研究可先完成 Python／Rust 現有能力映射；若要驗證，用暫存合成目錄測正常讀取、symlink／path escape、grant 撤銷、offline、取消與結果 parity。只有真 caller 需要此邊界且 Rust 接入提供實證收益才解凍。資料夾需求與 Rust 實作選擇分開：需要讀檔不自動證明需要第二個 backend。

## RT-011：先辨識遺忘原因

| 合成情境 | 要驗證的現象 | 應採取的方向 |
|---|---|---|
| 早期說明目標，超過 restore 的六組完成對話，再要求繼續 | 重啟／新 turn 的 request 是否仍含必要目標 | 先檢查目標保存與選取；摘要只是候選方案 |
| 保留目標與授權，插入大量已完成 observation | 是否為合法超限，壓縮後能否保留必要內容 | 有實測收益才做 summary |
| 一輪產生兩個合法 tool calls | 是否再現 AR-06 continuation failure | 修 native shape 相容性，不能以 summary 掩蓋 |
| 摘要來源在生成中被更正／刪除 | 舊摘要是否仍能送入新 request | source revision fence／失效；不把舊值重新寫回 memory |

評估以 captured request 中的目標、授權、來源與 pending pairs 為確定性基線，模型回答品質另列測試；不能只憑一句「她好像忘了」推論摘要有效。可全用合成資料，不需要使用者提供私人紀錄。

## 後續交付邊界

下一個可做的研究產出是 RT-015 的候選產生／來源失效契約與合成案例清單；不是 production timer、也不是自動 memory writer。RT-013 保持待需求，RT-011 先做反例分類。所有實作仍遵循 DEFERRED_TASK_PLAN 的 gate。

CI 格式或資產 provisioning 是工程驗證責任，不需要使用者協助；本輪未重跑 CI，未宣稱格式失敗已確認或修好。已知 AR-07 是資產準備缺口，不能混稱格式問題。
