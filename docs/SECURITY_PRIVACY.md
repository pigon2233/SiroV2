# SIRO 2 安全、隱私與資料生命週期

狀態：威脅與控制基線 v1。此規格用於產品設計與驗收，不聲稱目前程式已安全，也不取代部署環境的專業安全審查。

## 1. 保護目標與信任區

保護資產：Identity、對話/記憶、原始音訊與影像、位置/感測資訊、密鑰、permission grants、電腦/設備控制、更新來源及審計紀錄。

| 信任區 | 預設信任 | 必要邊界 |
|---|---|---|
| Core data directory | 本機擁有者與 Core service | OS 權限、單一主要 writer、備份加密選項 |
| UI/renderer/audio | 可顯示必要狀態，不可信任其授權決策 | 短效 session、最小 snapshot、輸入驗證 |
| Runtime/skill worker | Runtime 可驗 grant；skill 預設不可信 | sandbox/resource scope、輸出限制、審計 |
| Device LAN | 網路本身不可信；只信任已配對 identity | 憑證/secret、replay/expiry、topic ACL |
| Compute worker | 只信任預先配對節點及指定 privacy scope | mutual authentication、lease、最小 job input |
| Cloud provider | 外部處理者，只送使用者允許資料 | 明確 route、資料縮減、預算、停用入口 |
| Plugin/update source | 未驗證前不可信 | hash/signature、版本/來源鎖定、staged install |

localhost 也不是自動可信；另一個本機程序可能連接 port。正式 remote 連線不能使用明文 token 或僅靠 IP allowlist。

## 2. 主要威脅與控制

| 威脅 | 典型路徑 | 必要控制與驗證 |
|---|---|---|
| Prompt/內容注入 | 網頁、文件、email、sensor payload 要求執行動作 | 所有內容是資料；Planner 提議、Policy 判定、Runtime 驗 grant；A14/A16 |
| 權限混淆 | 模型輸出 `allowed=true`、修改 args 後沿用確認 | 簽署/不可偽造 grant、args hash、scope/expiry/use count；A14 |
| 路徑/命令逃逸 | `..`、symlink、shell 拼接、child process | canonical path、argv API、scope、process group、limits；A16 |
| 重放與雙重副作用 | broker redelivery、timeout retry、舊 MQTT retained command | idempotency ledger、expiry、readback、unknown outcome；A04/A18 |
| 跨身份資料洩漏 | memory/vector query 未先做 scope | identity/person filter、索引隔離、跨 scope fixtures；A11 |
| UI/WS 劫持 | 惡意 Origin、本機其他網站、長效 query token | Origin/session validation、短效 token、TLS/隧道；T10 |
| LAN 節點冒充 | 假 compute/device 廣播 | 預先配對、雙向認證、trust scope、revocation；A23 |
| Plugin 供應鏈 | skill/update 換檔、依賴遭污染 | 鎖版、來源/hash/signature、隔離驗證、last-known-good；A15/A20 |
| 資源耗盡 | 無限輸出、事件洪水、模型 OOM | 有界 queue/output、quota、governor、circuit breaker；A05/A15/A21 |
| 感測/視覺誤判 | 舊 frame、低 confidence、UI 變動 | timestamp/TTL/confidence、重新觀察、操作 readback；T24/T26/A18 |
| Log/備份洩密 | prompt、token、聲音進 log/公開 evidence | 脫敏、內容分級、secret scanning、一致加密備份選項 |
| 惡意自我修改 | 候選 skill 提權或 patch policy | 不在 production 原地改、獨立 workspace、policy 保護、審閱/既有發布政策；A19/A20 |

## 3. 資料分類與路由

| 分類 | 例子 | 預設保存／外送 |
|---|---|---|
| Public | 公開專案資料、公開網頁 | 可依任務 route；仍記來源 |
| Personal | 日常偏好、一般對話、裝置名稱 | 本機；只送已允許 provider 的必要片段 |
| Sensitive | 私人文件內容、位置、螢幕、音訊、相機 | local_only；使用者針對來源/目的地允許才外送 |
| Secret | API key、密碼、session cookie、private key | secret store；不進 LLM、Memory、log、evidence |
| Control | grant、action ledger、audit、update manifest | 本機受保護；只送必要驗證資料給可信 executor |

事件的 privacy 是資料上限，跨來源合併取最嚴格值。摘要不能自動降低分類；從 sensitive 原文生成的摘要仍 sensitive，除非有獨立可驗證的去識別流程。Provider adapter 在送出前產生可稽核的 disclosure record：目的地、資料分類、使用目的、大小、policy version，不記 secret/全文。

## 4. 收集、保存、刪除與匯出

- 原始 mic frame：僅 ring buffer，正常結束立即丟棄；使用者明確開啟診斷錄音時另顯示指示與期限。
- 原始 camera/screen capture：按需或變化觸發，分析完成後清理；不得默認加入 Memory。
- transcript/conversation：依 profile 保存；可設定不持久化單次對話。
- observations：只保存建立 world/memory 所需欄位及 TTL；高頻 raw telemetry 做彙總。
- memories/identity：直到使用者刪除或匯出後重置；保留 provenance/revision。
- audit/action ledger：預設本機 90 天，critical action 可更長；期限在 T00 部署政策確認。
- operational logs：預設 14 天並輪替；不含內容的 metrics 可 30 天。實際值皆可設定並顯示。
- backups：保留數量/期限可設定；刪除資料後 UI 必須說明舊備份可能仍含資料及到期時間。

刪除流程：標記寫入停止使用 → 移除 FTS/vector/summary 衍生物 → background physical purge → 產生不含內容的 tombstone/audit。取消 purge 前只能恢復尚未實際清除的資料；UI 要說明狀態。匯出使用版本化格式和 manifest/hash，secret、cache、模型權重預設排除。

## 5. 密鑰與身份驗證

Secret store 優先使用 OS credential store；headless 環境採權限 0600 的獨立加密或注入機制，實作前需 ADR。Repo 只放 `.env.example` 欄位名，不放真值。程序只取得完成自身工作所需的 secret；renderer/LLM 不應取得 HA、Runtime admin 或 update signing secret。

節點、設備、UI session 與 provider credential 分開輪替。撤銷後停止新工作，in-flight 依風險取消或完成並記錄。認證失敗不回顯 credential；logs 保留 actor、target、reason code 和 trace id。

## 6. Kill switches 與安全狀態

本機固定入口至少提供：停止語音輸出、關閉麥克風/相機、停止主動行為、禁止 cloud、停用所有第三方 skills、停止設備/電腦寫入、進 safe mode。這些控制直接走可信 control path，不需要模型同意或理解。

失去 Core、Policy、Runtime、broker 或時鐘可信度時，不開始新的寫入型 action。已在物理世界發生的狀態透過 readback 呈現，不在重啟後盲目補做。安全告警可繞過社交 quiet hours，但仍受音量/視覺通知政策，且不能挾帶一般主動聊天。

## 7. 安全驗收與發布門檻

T02/T10/T21/T22/T23/T26/T36 各自建立對應負面 fixtures；T35/T40 重跑。發布前至少完成：

- 依賴與第三方資產版本/授權清單，漏洞與更新策略有記錄。
- secret scan、設定檔權限與 log/evidence 脫敏檢查。
- A04、A11、A14–A16、A18–A21、A23/A24（v1.1）通過。
- local-only route 的網路阻斷測試證明沒有外送。
- kill switches 在 LLM/renderer 無回應時仍有效。
- backup/restore 在加密/未加密的實際部署設定下演練。
- 威脅模型隨新增 adapter、skill capability、遠端入口或資料種類更新。

安全發現依影響分類；任何已知未授權資料外送、scope escape、重複 destructive action、不可停止的自動控制或更新完整性失敗，都是 release blocker。
