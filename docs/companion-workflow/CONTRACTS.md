# 跨視覺／程式邊界的草案契約

狀態：**DRAFT，待 CP-00 對應現有程式後確認**。以下欄位是設計要求，
不是已存在的 API／事件／DB schema，不得直接拿去呼叫生產服務。
由 Claude 先核對現有 DTO／journal，提供窄 adapter；需要 public protocol 變更時
先經 DECISIONS、相容與契約測試，不在本規劃直接升版 Body v1。

## 1. 資產交付

Codex 交付每包需有下列 manifest 資訊（最終檔名／schema 由 CP-00 固定）：

| 類別 | 必備欄位／語意 |
| --- | --- |
| 身分／版本 | pack_id、version、asset digest、角色 identity 對應、來源與授權、建立工具版本 |
| 相容 | renderer／SDK／模型版本、可編輯工程索引、下載／取得方式與每檔 hash |
| 檔案 | moc3／model3／texture／motion3／expression／physics 等實際使用檔案；不夾可執行程式 |
| 能力 | supported activities／expressions／gaze／lip，unsupported 明列；不憑檔名推定支持 |
| 動作 | motion_id、entry／loop／exit、duration、fade、可中斷／恢復規則、接地與位移曲線 |
| 參數 | 真 parameter ID、合法範圍、channel mask、混合規則、優先序與缺參數處理 |
| 成本 | 實際 texture 尺寸／數量、模型／動作大小、測得記憶體／frame cost 與測試主機 |

Codex 提供資料與驗收情境；Claude 寫 loader／validator，不讀取任意 JS 或執行資產內程式。
套用前驗 hash／路徑／大小／相容，活動安全點切包；失敗維持已驗舊包並明示原因。
保存目前最新情緒，說話嘴型使用有效音訊狀態，不因切包重播聲音或重設人格。

## 2. 動作控制的權責

| Channel | 唯一來源 | 互斥／保留規則 |
| --- | --- | --- |
| 身體主活動 | presentation 活動控制器 | 一次一主活動；取消移動不停止表情／有效音訊 |
| 桌面 root 位移 | desktop scene controller | 與局部步態同步；Core 不收像素座標 |
| 表情 | Core affect 的既有投影 | 動作無權自行改持久情緒；缺表情回有效支援值並標示 |
| 視線 | 經仲裁的注意力／使用者互動 | 不能與 SDK drag 同時無仲裁搶參數 |
| 嘴型 | 唯一 audio owner 的有效播放訊號 | 真音訊無法取能量時標示限制，不用隨機嘴型假裝同步 |
| 呼吸／眨眼／物理 | 本機 renderer | 接受 mask，明確混合／抑制；不掩蓋閉眼等主動作意圖 |

活動意圖至少需有 instance_id、generation／epoch、activity kind、asset version、
可選 parent run、有效期限與中斷語意；具體 wire 形狀待定。
renderer 回 accepted／started／finished／interrupted／unsupported／failed 必須帶原識別。
「動畫閱讀中」不能變成「實際 HTTP 已開始」；動畫完成也不能替工具提交成功。
重連僅投影最新有效狀態，不回放過期動作或事件觸發 TTS。

SDK 動作結束 callback 用於非循環正常完成；循環、覆寫、中斷情境由活動控制器明確終結，
不可永遠等 callback。參見 [官方 callbacks](https://docs.live2d.com/en/cubism-sdk-manual/callback-motion-end-web/)
與 [motion 設定](https://docs.live2d.com/en/cubism-editor-manual/motion-setting/)。

## 3. 活動與可追溯性

| 欄位群 | 必須可對映的資料 |
| --- | --- |
| 關聯 | activity_id、parent_activity_id、run_id／turn_id／proposal_id（適用時）、event_id |
| 發起來源 | owner_request／self_interest／scheduled_followup、來源引用、原因的簡短可理解摘要 |
| 狀態 | proposed／queued／running／paused／cancelling／completed／cancelled／failed／unknown |
| 結果 | tool name、脫敏目標／參數、exit code／錯誤類別、結果摘要、產物與來源引用 |
| 排序／時間 | durable sequence／revision、顯示用時間、同主機 monotonic duration |
| 權限 | source privacy、scope／permission revision、所用工具政策，不保存 credential |

上述是 view 模型，不要求把現有 run 狀態欄改名或覆寫。活動與 run 可一對多，
每次 resume 要有新 attempt 與同一活動的明確關聯；不重用 provider call ID 當全域唯一鍵。

狀態規則：queued 可進 running／cancelled；running 可進 paused／cancelling／終態；
cancelling 只有 reliable readback 才轉 cancelled。若操作剛好已完成，保留實際 completed，
同時記錄取消競態，不捏造取消成功。讀不回用 unknown，不是 completed 或 cancelled。
終態不可因舊 started／delta 回到 running；event 重送去重且不重新 dispatch。
unknown 經明確 reconciliation 可得到終態；completed／cancelled 等既定終態的更正另記新 revision，
不得無痕改寫歷史。暫停／恢復不能把已完成副作用當待重做步驟。

## 4. 網路 metadata 與監測覆蓋

| 類型 | 可顯示 | 不應宣稱 |
| --- | --- | --- |
| Tool audit | 真正 dispatch 的工具／目標／結果、關聯活動 | 僅憑命令文字知道所有子程序連線 |
| Network adapter audit | 有攔接能力的 HTTP／browser request，redirect chain、method、origin、status、耗時 | adapter 之外沒有流量、一定掌握 HTTP/2／TLS 內每個細節 |
| Cache／拒絕 | cache hit／blocked／failed 與理由、是否實際連線 | cache hit 等同新請求，或 blocked 等同讀取成功 |
| 程序觀測（選配） | 各平台實際支持的 process／destination／流量量測 | 未實作即稱 Wireshark 全覆蓋，或把連線 bytes 當已解密內容 |

每個 activity 顯示 coverage、last_updated 與 completeness／gap；無 metadata 顯示 unavailable。
工具容器內可能包含多個 HTTP request，不能強迫一 tool 等於一 request。
redirect 的主請求／子資源各按 adapter 能力顯示；未知 query／header 預設不保存。
狀態碼未知就未知，不從網頁 title 推出 200。browser／shell 已有內容不重抓只為填滿畫面。

UI 範例欄位：14:20:03／自主研究／搜尋星雲／延續昨天興趣／完成。
這是合成設計示例，不是目前 SIRO 曾做過的事情。

## 5. 儲存、補讀與故障

- 使用既有 durable owner 儲存業務狀態；讀取投影不成為新執行權。需要新增 audit metadata
  時由 Claude 定 migration／retention，必須相容且帶 error-path 測試。
- 目標 read page 最多 100 rows，view 保留最多 500 rows；durable retention 初值 7 天／
  10,000 audit events，任一先達即清理可丟棄 audit 詳情，保留既有 durable run／mutation。
  這些是待驗初值，不改既有 journal 保存規則；不得刪 active run 關聯或 owner facts。
- 終態與結果先持久，再發布；前置 dispatch audit 寫失敗時不開始新的自主外部操作。
  執行後持久失敗必須告警與 unknown／reconcile，不因無紀錄就重送副作用。
- UI 以 snapshot high-water cursor 後接增量，處理重疊、亂序、去重、斷線與 gap。
  snapshot／journal 不是重播執行來源。buffer 有界，overflow 必須明示補讀／降級，不靜默漏記。
- 認證／session／owner 隔離沿既有規則；查看任務不取得執行權，過期 revision 控制必須拒絕。
- 持久去重使用 activity／revision／動作識別；不能只存在 browser Set，刷新就失效。

## 6. 停止與前景優先

| 控制 | 語意 |
| --- | --- |
| 停止此活動 | 取消指定 instance／generation 的工具、待播語音與動畫；顯示停止中後回讀 |
| 暫停自主探索 | 不再排新的自主業務；在跑的工作依明示策略保留／取消，不能隱含兩義 |
| 停止全部背景 | 停止所有 background scope，不誤取消獨立有效前景 run |
| 原全域停止 | 維持既有承諾，取消當前有效回覆／工具／TTS；不可被新增背景 owner 繞過 |

新前景 turn 到來讓背景工作釋出有界資源；不靠無限排隊等待模型／GPU。
停止後 delayed provider、tool、network、TTS、motion 回呼都須按 ID／generation 驗證。
程序取消／終態持久完成與可見 UI 完成分開量測；原 sleep 案例需覆蓋停止前／中／後、
刷新／新 turn／重啟／斷線，保留新對話正常。

## 7. 情境觀察與研究筆記

每筆 observation 帶 source、observed_at、expires_at、confidence、privacy、permission_revision。
過期／撤權後不可用於新的主動決策；來源更正影響依賴筆記與摘要，沿既有 memory invalidation。
畫面分享／app metadata／檔案可見性分別啟用；不開相機／麥克風補猜活動。

研究筆記含來源 URL／取得方式與時間、引用位置、摘要、推測與待查項，
共用原記憶服務入口但分類獨立；不能直接提交為使用者 facts 或不透明人格更新。
主動分享帶有相關來源；沒有 evidence 時可以問「你是在寫程式嗎」，不能宣稱已知道。
