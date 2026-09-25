# SIRO 2 使用體驗與設定規格

狀態：產品體驗基線 v1。這份文件定義使用者實際會看到、聽到和控制的流程，避免後續只完成後端模組而沒有可用產品。

## 1. 角色與使用模式

第一版只有一位擁有者和一個 SIRO Identity。訪客可以在擁有者啟用後對話，但不自動取得私人記憶、電腦或設備權限。多身份、多家庭成員和兒童模式不在 v1.1 範圍；資料結構需保留 person scope，避免日後無法隔離。

使用模式：

| 模式 | 能力 | 明確限制 |
|---|---|---|
| Setup | 本機初始化、選模型/語音/身體、測試裝置 | 不執行主動行為或系統動作 |
| Companion | 對話、身體、記憶、已授權技能與設備 | 遵守安靜時間、成本與 privacy policy |
| Focus | 回應明確呼叫與重要告警 | 抑制非必要主動聊天、Dream 可背景執行 |
| Private | 本地規則與 local-only 能力 | 不送雲端、不保存原始音訊／影像 |
| Safe mode | 文字、本地狀態、唯讀診斷 | 停用第三方技能、設備寫入及自動更新 |
| Maintenance | 備份、升級、還原、診斷 | 新對話與新動作暫停或明示降級 |

模式轉換必須可見並記錄來源。網路斷線、模型故障或資源不足只會進 degraded state，不能偷偷改變 privacy 或權限。

## 2. 首次設定流程

1. `siro doctor` 顯示 OS、音訊、GPU、broker、資料目錄與尚缺項目。
2. 使用者建立 Identity：名稱、稱呼、語言、時區、初始人格摘要。Immutable core 會顯示哪些項目只有擁有者能改。
3. 選資料政策：local-only 或允許指定 provider；顯示將外送的資料種類，不以一個總開關模糊處理。
4. 設定模型：先測文字，再測 streaming/cancel。失敗時可保留 mock/離線模式，不阻止完成其他設定。
5. 設定身體和聲音：選合法資產，分別預覽表情、口型、語音與停止播放。
6. 測試麥克風、輸出裝置及打斷。若 AEC 不可用，介面顯示耳機或半雙工限制。
7. 選擇主動性：預設關閉；啟用時設定 quiet hours、每日上限、Focus 行為。
8. 配對 skills/devices：逐項顯示 scope、風險與撤銷入口，不批次授予 root/admin。
9. 執行 setup checklist，成功後進 Companion；缺外部硬體可標記稍後設定。

Setup 每一步可返回、跳過非必要項目、重新測試。密鑰只寫入 secret store；畫面和 log 只顯示 provider、key 尾碼及最後驗證時間。

## 3. 日常主要流程

### 3.1 對話與打斷

UI 顯示 listening、thinking、speaking、using tool、waiting permission、degraded、offline。使用者開始說話時 SIRO 應停止自己的音訊並保留已說到哪裡；取消後不再播放舊 turn。模型失敗時顯示可理解的結果與可用退路，不吐 stack trace。

重要訊息要區分：

- 「我聽到了」只代表輸入完成。
- 「我正在處理」代表 goal/action 已建立。
- 「完成」只能在動作 readback 或持久結果確認後顯示。
- timeout 後結果不明顯示「結果未知」，提供查詢狀態或人工確認，不能寫成失敗後自動重做。

### 3.2 權限與動作

詢問介面顯示：SIRO 想做什麼、目標、必要資料、風險、期限、可撤銷或補償方式。選項為拒絕、只允許這次、允許此範圍至指定時間；不提供模糊的「永遠允許所有操作」。參數改變、目標改變或 grant 過期就重新判定。

長任務顯示 goal、目前步驟、已使用時間/工具次數、取消與等待原因。取消只停止可停止部分，對已發生的外部效果顯示真實狀態。

### 3.3 記憶

Memory 面板至少提供搜尋、來源、類型、建立/更新時間、可信狀態、關聯對象、更正、刪除。使用者更正後保留 revision 供稽核，但正常檢索不再使用失效值。推測、外部來源、使用者明確陳述與 SIRO 自身經歷使用不同標籤。

刪除前顯示會受影響的摘要/索引與備份限制。匯出產生可攜的 Identity、Memory、Relationship、Skills metadata；不默認包含密鑰、模型權重或原始錄音。

### 3.4 主動行為

主動訊息在 UI 標示觸發理由，例如「未完成提醒」或「房間狀態變化」，使用者可針對該類型靜音、調低頻率或回報不適合。安全告警與社交發言分開設定；不得把社交 drive 包裝成緊急告警繞過 quiet hours。

### 3.5 設備與電腦

Device 面板區分 online、offline、unknown、stale；操作後顯示 command accepted 與 state confirmed 兩個階段。Computer 面板顯示支援能力、scope、正在執行的 action、最近審計和 kill switch。停止所有自動化是本機可用的固定控制，不能依賴 LLM 回應。

## 4. 最小畫面與入口

| 畫面／入口 | 必要內容 | 對應任務 |
|---|---|---|
| Setup/Doctor | 環境、Identity、provider、body/audio、資料政策 | T00、T07、T12、T16、T34 |
| Companion | 身體、字幕、狀態、文字輸入、mic、cancel | T08、T10、T12–T16 |
| Activity | goals/actions、工具步驟、結果未知、取消 | T19、T21–T25 |
| Memory | 搜尋、provenance、更正、刪除、匯出 | T17、T18 |
| Skills | manifest、權限、版本、啟用、隔離狀態 | T22、T30–T32 |
| Devices | 狀態、位置、能力、command/readback | T26–T29 |
| Privacy & Permissions | provider routing、grants、retention、audit | T07、T17、T21、T38 |
| System | service health、resources、profile、backup/update | T32–T40 |
| CLI | doctor、headless chat、diagnostics、backup/restore | T01、T08、T34 |

第一版可以將多個畫面合併在同一個本機控制 UI，但所有入口與資訊仍須可找到；不可用只有開發者看得懂的 log 取代使用者狀態。

## 5. 通知、錯誤與無障礙

錯誤訊息包含發生項目、已知影響、資料/動作是否確定、可採取的下一步、trace id。相同服務故障合併通知，恢復時提示一次，不反覆語音播報。高風險或 privacy 降級不得只以動畫表示。

字幕不得依賴顏色區分 user/SIRO/status；控制有文字 label、鍵盤可操作、焦點可見。提供 reduced motion、動畫/語音獨立關閉、字幕保留時間與音量設定。UI 應支持繁體中文；內部錯誤碼保持穩定，顯示文字可本地化。

## 6. 設定層級與優先序

優先序由高到低：啟動參數（本次）→ user profile → deployment profile → built-in defaults。secret 不進一般設定。未知欄位拒絕或明確警告，不靜默拼錯；設定 schema 有版本及 migration。

最低設定群組：identity、locale/timezone、privacy/provider routes、model budgets、body、audio devices、memory retention、proactivity、permissions、skills、devices、resource thresholds、logging/telemetry、backup/update。設定變更若需重啟應在套用前顯示；能 hot reload 者需原子切換，失敗回舊值。

## 7. 體驗完成條件

除 [ACCEPTANCE.md](ACCEPTANCE.md) 的功能案例外，v1.0 必須完成首次設定、Companion、Memory、Permissions、System 五條人工 walkthrough；v1.1 再完成 Devices 與 distributed node walkthrough。每條流程以沒有開發者口頭指導為目標，記錄阻塞、誤解、耗時及使用者評分。任何高風險動作、結果未知或 privacy route 都要在畫面可辨識。
