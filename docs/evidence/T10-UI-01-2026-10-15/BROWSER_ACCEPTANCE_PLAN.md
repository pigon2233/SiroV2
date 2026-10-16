# T10-UI-01 自有真 HTTP／瀏覽器驗收準備

2026-10-15。此文件是操作方案；準備時沒有開伺服器或聲稱產品已 PASS。

## 啟停與已確認依賴

在 repository root 執行 `.venv/bin/python -B docs/evidence/T10-UI-01-2026-10-15/product-probe.py --check-only` 只檢查依賴，不建立 HTTP 服務。現有 Python 3.14.4、Playwright、系統 Chrome `/opt/google/chrome/chrome`、Node 24.21 與已編譯 `target/debug/siro-runtime` 可用；Playwright 預設 Chromium path 可解析但 executable 並未下載，runner 明確用現成 Chrome fallback。本輪不安裝依賴、不下載模型或資產；檔案存在檢查不等於 browser launch 已驗。

需要驗收時，執行同一命令、移除 `--check-only`，保持 stdin 可寫。第一行 JSON `ready` 提供新的 random loopback URL；只能開該 URL，不開 live 8026。fixture 的 temporary account、workspace、SQLite、Runtime ledger 全部自有。`notes.md` 包含兩筆合成 TODO；`later.md` 用於未批准跨重啟案例。

輸入 JSON line 控制生命週期；`{"command":"restart"}` 會先等待真 shutdown／Rust child join 與 runtime temporary cleanup，再用同一自有 SQLite 啟動。`{"command":"finish"}` graceful stop、join 並刪除 temporary tree；正常回覆包含 `temporary_removed:true`。例外或 stdin EOF 也走 finally cleanup。不要用關 browser 代替關 server。

最終以此目錄 `RESULTS.json` 與 `cycle-*.log` 核對載入來源、served HTML/script hash、正確 Rust executable、configured roots、讀取數、程序 join 與 temporary cleanup。程式不會把手動瀏覽器行為自動寫成 PASS；瀏覽器證據另記。

啟動後可另外執行 `.venv/bin/python -B docs/evidence/T10-UI-01-2026-10-15/browser-navigation.py --url http://127.0.0.1:<ready-port>/`。它只接受明示的 127.0.0.1 random port（拒絕 8026）；用真 Chrome、真 link click 與現有 HTTP／WS，驗九個互斥畫面、同 iframe、draft、history／direct hash／reload、導航零 mutation／新 socket，以及 320／375／414／768 px 三畫面 overflow／截圖。它不建立或批准 goal，不呼叫內部 handler，不 mock API；結果在 `BROWSER_RESULTS.json`／`browser/`。執行前狀態是 NOT_RUN，不把此處操作方案當 PASS。

## 真實與合成邊界

沿用既有 D57 `product/product-probe.py` 與 `test_release_source_process.py` 的只讀 helper；current source 複製後啟動 actual product launcher/main、Gateway、GoalService、SQLite persistence 與 Rust filesystem.read，API 不 mock。唯一 instrumentation 是 synthetic account locator 與 loaded-source observation；可在 RESULTS 核對。只讀取 public source 與 fixture；不讀原服務 DB、聊天、key、私有模型、GPU，不送 provider／TTS request。

renderer 是明示的 `prepared-renderer` 文字 placeholder；這不構成 Live2D、嘴型、情緒或原生桌寵驗收。上述項目保持 NOT_TESTED。聊天頁只驗現有 draft／導航／控制狀態，不送合成模型請求來冒充回覆品質。

## 建議完整操作：三次真 main 啟動

1. Cycle 1：真 browser 開 ready URL，確認 default 對話畫面。輸入但不送出 draft，逐一透過可見導航前往任務／記憶／能力／電腦／技能／設定，再回對話；只一個主要工作區可見，draft 不丟。保留 desktop 截圖、console error、HTTP failure。建立 `notes.md` 待審任務，畫面顯示範圍／批准與未讀取；輸入 `{"command":"checkpoint","name":"first_proposed"}`，預期實際 Rust read 0。跨頁、back／forward後再取 `{"command":"navigation","label":"proposed-after-navigation","expected_reads":0}`，不能因導航執行或批准。
2. 輸入 restart。Cycle 2：重新載入同 origin，任務頁人工重新查詢；`{"command":"checkpoint","name":"reopened_proposed"}` 應是原 goal_id／revision／proposed／0 reads。透過真可見批准按鈕批准一次；看完成結果與 `notes.md`／line 2、4／SHA／time。輸入 `{"command":"checkpoint","name":"first_completed"}` 應是一筆 read、steps 1。跨頁／查詢／back-forward後 `navigation` expected_reads 1，不增加 POST／批准或讀取。另建立 `later.md` 不批准，`{"command":"checkpoint","name":"second_proposed"}`。
3. 再 restart。Cycle 3：手動查詢 `{"command":"checkpoint","name":"third_reopen"}`；原結果保持 completed，later 保持 proposed，而此新 runtime read 0，證明啟動不自動重播。需要時執行 `{"command":"correction"}`：此明示 API 操作只改合成 notes、建立並批准新 goal，驗證舊 observation 保留、corrected source 使用新 SHA／line，wrong revision 409／其他 session 404，不冒充 UI 行為。最後 finish，確認每輪 join／cleanup。

每次 `snapshot`／`navigation` 都是 GET/readback。browser 的 console／network 記錄不得包含 Authorization token；若另寫 Playwright runner，輸出 method、pathname、status、計數即可，不能 dump request headers。

## 畫面與導航驗收

- 逐頁 root／直接 hash／返回／前進／reload，顯示主要 workspace 唯一；導航用真元素與可見文字，不呼叫內部 JS handler 代替點擊。
- 確認共用 session、control WebSocket、音訊／renderer element 不因切頁新增；網路紀錄以連線次數與 mutation count 作證，不把單純 DOM snapshot 當 owner 證據。
- 可見的 cancel／停止工具在各頁可鍵盤到達；現有 auth、stale revision／late response／unknown 行為仍由原 frontend tests 與真 API 負向案例覆蓋。
- desktop、320／375／414／768 px、200% zoom 或等效明確設定各留 screenshot 與 overflow 量測；輸入繁中長字串，不把固定短內容通過當一般長內容通過。
- 全程不可用第二頁的 hidden panel 假裝「只一個工作區」；同一 renderer host 的生命週期要由真 DOM／network 觀察。未執行的 keyboard、對比、reduced-motion、人耳／角色／原生桌面一律 NOT_TESTED。

## 失敗處理

保留第一個 failing screenshot／console／assert 與 cycle log，不覆蓋成全綠。修正前端後需關閉 fixture、重新複製 source 啟動，不在執行中的 bundle 熱改；RESULTS 會綁定 served source hash。測試只把自己的 process terminate／join，不對其他進程掃殺。重跑前把既有此目錄結果移入具名失敗子目錄，避免 log 被覆蓋。
