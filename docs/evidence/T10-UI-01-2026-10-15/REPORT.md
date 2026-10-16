# T10-UI-01 第一個網頁改版切片

日期：2026-10-15（Asia/Taipei）。基準 `215aaa9d305073b41a44f242387051ea836dc035`，工作區包含上一輪規劃文件變更。結果：**網頁導航／既有功能移轉切片 LOCAL_VERIFIED；T10-UI-01 整體 PARTIAL**。沒有正式部署、Git 發布或私人服務重啟。

## 可見成果與修改範圍

唯一 production 修改是 `src/siro/services/presentation/static/index.html`：淺色視覺、共用導覽與九個獨立工作畫面（對話、任務、記憶、能力、電腦、技能、設定、權限、系統）。有限 `#/name` 路徑支援直接進入、後退／前進與重整；未知 hash 回對話，不解譯／回顯 hash 內容。

原 DOM 保留；未顯示的畫面 hidden＋inert。原 session、socket、iframe、播放器與任務輪詢沿用，沒有新框架或平行 owner。停止回覆／語音與麥克風控制位於共用工具列；電腦提案以可達提示引導，不搶走正在輸入的頁。電腦捷徑及技能範例會返回對話後再填入，不自動送出。長頁切換會將鍵盤焦點移到可見標題；工具列保持可達。

直接開 `file:` 是唯讀介面預覽：明示尚未連接服務、停用執行控制，不建立 session 或 socket；實際對話／任務仍須從 SIRO HTTP 服務開啟。沒有為預覽放寬 Origin、token 或 grant。

新增 `tests/integration/test_frontend_navigation.py`，原 tracked tests 全部保持。Core、Gateway、Rust、DB／SQL、權限、provider、模型／聲音、資產及 dependencies 均未修改。UI source SHA256 與驗收來源一致，見 [ACCEPTANCE_SUMMARY](ACCEPTANCE_SUMMARY.json)。

## 已執行的驗收

| 範圍 | 實際結果與證據 |
|---|---|
| 新導航／生命週期 | **24 PASS / 1.49s**，真頁面腳本＋合成 DOM／socket／audio；含九條直接路徑、未知 hash、歷史、焦點、待送出請求、待批准、隱藏頁串流、播放中切頁及全局取消、file 預覽零請求。[navigation-tests.log](navigation-tests.log) |
| 原前端相鄰回歸＋新案例 | `.venv/bin/python -m pytest tests/integration/test_frontend_*.py -q`：**333 PASS / 21.21s**，未新增 skip，未改原測試。[frontend-regression.log](frontend-regression.log) |
| 新測試靜態檢查 | Ruff check PASS；三份新 Python 檔 format check PASS；mypy 新測試檔 PASS；`git diff --check` EXIT0。[ruff.log](ruff.log)、[mypy.log](mypy.log) |
| 真瀏覽器導航 | 使用 CUA／In-app Browser，非 mock API。**24 份 DOM 檢查**，每次恰一個工作頁可見，其餘 hidden／inert，唯一 renderer element／全局停止控制；實際點擊、返回／前進、鍵盤 Enter、草稿跨頁保留。[CUA_CHECKS](CUA_CHECKS.json) |
| 響應式 | **320／375／414／768px × 對話／任務／設定，共12份檢查**，root 無水平溢出；另有1440px與預設桌面畫面。截圖包含 [320任務](tasks-320.png)、[768設定](settings-768.png)、[最終任務](tasks-final.png)。不是所有頁／內容的完整無障礙認證 |
| 文字對比 | 已宣告主要文字／背景 token 組合達4.5:1；只驗這些組合，不代表所有 disabled／互動狀態通過。[TEXT_CONTRAST](TEXT_CONTRAST.json) |
| 真產品與持久任務 | 自有 temporary main／HTTP／Rust／SQLite，三次啟動：先待審0讀取→重啟仍原ID／revision→UI明確批准一次→讀取1次且保行2／4與SHA／時間→另建未批准任務→再重啟，舊結果保持、新任務不自動讀取。[RESULTS](RESULTS.json)、cycle logs |
| 導覽無副作用 | 全頁導航與歷史後仍0讀取；批准完成跨頁保持1讀取；第三輪導航維持新 runtime 0讀取。server log 除 session 外，只有兩次明確建立任務與一次明確批准的 POST。[NETWORK_SUMMARY](NETWORK_SUMMARY.json) |
| source-only 回退 | 自有隔離複本放回精確舊 HTML，新畫面隔離案例真 RED；重套目前 HTML 真 PASS，root UI 與資料完全不替換，temp 已清。[ROLLBACK](ROLLBACK.json) |
| 清理 | 三輪服務與 Rust child 全部正常停止／join，runtime temp 及整個自有資料樹已移除；自建瀏覽器頁已關閉、viewport override 已 reset，使用者原分頁保留 |

第一輪全頁導航的 server log 只有1次 renderer GET、1條 control 連線。後續輪含手動 reload、服務重啟、失效分頁更換及重連，不能把每輪累計連線數當成「完全無重連」；合成測試另外檢查純導航不替換 owner。沒有送出真模型、TTS 或麥克風請求。

## 保留的失敗與修正

- 首次新測試組：9 FAIL／104 PASS。新合成 DOM 不支援複合 selector，且原任務標題的靜態檢查發現標題被移出面板。導航聚焦改為直接取目前 pane 的 heading，並保留清楚的任務面板標題；未改舊 assertions。[first-tests.log](first-tests.log)
- 第二次：2 FAIL／111 PASS。新 harness 缺 DOM `replaceChildren`；另一個新案例錯把 HTTP response 當作 turn owner。既有 ordered control stream 才是 owner，production 無此 bug；補完整合成 DOM、以真 `turn_started` 驗導航及不信任 HTTP turn ID。[second-tests.log](second-tests.log)
- 首次 fixture 啟動失敗：新 wrapper 的 credential-name filter 誤刪非秘密 token-budget 設定，main 在啟動前拒絕。只保留明確的合成設定，不改產品 gate；原 finally 已清 temp。[first-harness-failure](first-harness-failure/SUMMARY.md)
- 第二次 fixture：手動操作較久後，fixture 自己快取的短效 token 收到401；產品瀏覽器仍正常完成新 session／待審操作。只在明確 fixture readback 前重新取得自己的 session，不改300秒產品TTL；失敗 log／receipt 與正常 shutdown 保留於 `second-harness-readback-failure/`。
- 瀏覽器重設尺寸後曾暫時無法截圖；重新觀察後成功。舊自建 tab 被清理及 helper 捕捉舊 tab handle，改綁當前分頁後重驗；不是產品任務丟失。CUA 對 `file:` 的直接導航被瀏覽器 URL policy 拒絕，未繞過；file 分支只有合成測試證據。

## 限制與接續

renderer 是**明示 synthetic prepared-renderer**；本輪沒有證明真 Live2D 隱藏／恢復後仍正確重繪、情緒／嘴型、跨視窗 owner 交接或螢幕自由活動。截圖不能冒充角色驗收。模型對話品質、真語音、人耳、200% zoom、完整 screen reader／reduced-motion、三輪真人體驗與正式部署均 NOT_TESTED。完整 `scripts/check` 未重跑，沒有將前輪 CI 套用到本改版。

獨立代理提供了初步生命週期／焦點／通知審查，但最終回合遇帳戶限制；root完成修正與實測，不宣稱獨立 final approval。第一版仍是單份有界頁面程式；本次保 DOM 解決相容性，未以改版新造全局 state 或抽象框架。

下一切片：沿 T12／Companion plan 驗**真 renderer 在切頁後恢復與唯一 owner**，再做任務清單／詳情密度、記憶搜尋及設定用語等產品補完。桌面宿主、全身／步態／動作製作與真正自由活動仍是分開的未完成交付；RI-005、FIX-002／005／006 舊 gate 不變。

回退方法：僅回退本 HTML source，保留所有 DB、對話、記憶及任務；新導航測試會如實 RED，舊產品／後端契約不變。不得因 UI 回退還原舊資料。全部證據只含公開 source 與合成資料；未操作 live8026、私人 DB／聊天／key／模型／GPU。
