# CP-V01 交付：實檔盤點與隔離自然度基線

2026-10-18 Asia/Taipei。**PARTIAL：盤點／合成事件的真 renderer 基線完成；真音訊嘴型與使用中宿主驗證未完成。**
本卡只在 design/companion/CP-V01/ 新增資料，既有 TASKS.md dirty 修改原樣保留。
Base feda8bc；branch design/companion-cp00-20261018（延續同一視覺工作區）。

## CP-00 接收

已接收 Claude 分支 claude/companion-cp00-receipt-20261018 @
f7f790c90066842abdae95a221bf49aa5e710ea1 的 CP-00-CLAUDE-RECEIPT.md。
接受其 audio owner／journal 定義處與 proactivity 無 production caller 的更正；
採用主 checkout 模型唯讀路徑，沒有搬移或提交模型／SDK／原始聲音。
這份回覆不改 Body v1，不接受新 migration。雙方 source 對映可續作，但 GitHub 共享認領／PR 仍未完成。

## 產出

- [INVENTORY.md](INVENTORY.md)：42 個參數、6 個掛載 motion、8 個 expression 與能力矩陣。
- [asset-inventory.json](asset-inventory.json)：47 個 Haru 目錄檔案 hash、掛載參照、表情 blend／值、來源／授權、bundle digest、manifest 56/56 比對。
- [parameters.json](parameters.json)：真 moc3 經 Core 取得的型別／合法上下限／default。
- [timeline.json](timeline.json)：六段共 36 樣本，全部 42 個參數及表情讀回，browser 版本與 fixture 說明。
- [mouth-cancel-readback.json](mouth-cancel-readback.json)：取消前後及新說話的嘴型／呼吸對照。
- [STORYBOARD.md](STORYBOARD.md)：entry／loop／exit／interrupt／resume、鏡頭、固定情境及 V02 輸入。
- [preview-artifacts.json](preview-artifacts.json)：本機 GIF、36 張原始畫面、接觸表與補充截圖的逐檔 hash／取得位置；尚未上傳遠端 artifact storage。

## 執行方式與隔離界線

診斷用 Node 24／既有 Playwright／本機 Google Chrome（版本見 timeline），不新增依賴。
以暫時 HTTP server 綁 127.0.0.1 隨機 port，唯讀提供主 checkout dist 的檔案；
/v1/session 回傳 synthetic token；browser init fixture 以 EventTarget 假 WS 注入 body v1 事件。
禁止接入真 /ws/body，不占用桌寵 lease，不連模型 provider、不讀私人記憶、不開 mic、不播聲。
Core 的 fromMoc 在 browser 記憶體加唯讀取樣 hook；bundle 與磁碟上的 Core／模型均未改。
Core 6.0.1 實際成功載入；WebGL 使用 SwiftShader，不能當 GPU／桌面效能證據。
精確事件順序與時間、讀回欄位見 STORYBOARD 與兩份 readback；重新載入可清除診斷 hook。
暫時 browser／HTTP server 已在 finally 關閉。

## 結果與缺陷

| ID | 證據層級／重現 | 參數／結論 | 後續 owner |
| --- | --- | --- | --- |
| V01-D01 | 隔離真 renderer，F03→cancel→新 speech，15 次讀回 | ParamMouthOpenY 取消前 0.5595～1，取消後 5/5 為 0，新 speech 後 5/5 仍 0；同時 ParamBreath 持續變化。對應 lappmodel.ts 每幀 _siroMouthOpen 覆寫，main.ts cancel 設 0 且 speech 無解除路徑 | Claude P01；先與有效 audio owner 契約對齊，不改回假嘴型 |
| V01-D02 | source＋主錄製 | body.speech 沒有嘴型驅動；主錄製 speech 段 mouth 全為 0。沒有音訊 fixture，不能聲稱真語音同步 FAIL／PASS | Claude P01 接有效音訊，再真語音重驗 |
| V01-R01 | asset 靜態確證，非視覺失敗 | 六個掛載 motion 都寫全部 42 個 ID，與 gaze／expression／mouth 交集；要分 mask，不能用整段全參數播放假裝隔離 | Codex V02 資料；Claude 混合器 |
| V01-R02 | 主錄製觀察，未評自然度分數 | happy F05 在 cancel／resume 後仍保留，呼吸不中斷；沒重現取消清表情或全身瞬間 default 重置 | 保留反例；不得沿 prepare 腳本舊風險宣稱已現場重現 |
| V01-R03 | source 確證 | body.gesture 無處理；TapBody 隨機函式非目前事件 caller。沒有點頭／閱讀語意能力 | Codex V02 曲線＋Claude P01 |

F05 閉眼是表情設計，不能把本次閉眼直接列為 blink 損壞。
主情境頭部達 30 上限，但本輪沒有對照去 gaze／去 motion 的實驗，不確診 channel 搶寫。
稀疏擷取不足判定逐幀跳動、細微關節破圖或自然度 4/5；不能用無 pageerror 取代視覺驗收。

## 驗證結果及失敗保留

- JSON 解析、參照 ID 對應真參數、模型 manifest 56/56 SHA-256：PASS。
- 本機真 Haru renderer 完成 36 張畫面／參數讀回，pageerror 0：PASS（合成 WS／無音訊）。
- F03 取消後 mouth pin：REPRODUCED，正式程式未修復。
- 第一輪診斷因 Core hook 未生效而等候逾時；追加 hook 受末行 source-map 註解吞掉，補換行後成功。
  另一次診斷 server 將根目錄當檔案回傳，navigation 失敗；修正映射後成功。這些是診斷 fixture 問題，不算 SIRO 缺陷。
- 沒有跑 production unit／全 scripts/check，因本卡不改程式；未將歷史測試數字挪作本卡成果。

## 剩餘驗收與回退

真有效音訊→mouth 能量、使用中宿主版本／DPI／實機自然度尚未驗；沒有重啟服務。
預覽 artifact 目前只在本機，跨機讀取尚缺版本化存放；Git 裡的 JSON 不替代可觀看畫面。
因此不把 CP-V01 整卡或 CP-00 完整環境 gate 標 DONE，也不開始 V02 正式資產製作。
下一步：Claude 接收 D01、提供可隔離的有效音訊測試路徑；對同版 source／asset 補嘴型與連續錄製。
回退只撤本卡資料 commit；本機預覽按 receipt 保留或移除，不影響目前模型、資料與服務。
