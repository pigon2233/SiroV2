# 電腦操控 Runbook（owner 之後實機驗證用）

全部預設關閉。不設 token＝後端路由不掛載，桌寵也不連線。

## 開啟步驟（每次都由 owner 手動）
1. 後端環境（WSL 啟動 SIRO 前設定）：
   - `SIRO_COMPUTER_TOKEN`：≥32 字元隨機字串（桌寵與後端要同一個）。
   - `SIRO_COMPUTER_ALLOWED_PROCESSES=遊戲.exe`：只允許操控的前景程序（空＝一律拒絕）。
   - `SIRO_COMPUTER_CLOUD_SCREEN=1`：同意把截圖交給雲端模型（claude CLI）；沒設則決策器拒絕送圖。
2. Windows 桌寵啟動前設定同一個 `SIRO_COMPUTER_TOKEN`。
3. 托盤選單 →「電腦操控：關閉（點此開啟）」。急停熱鍵 `Ctrl+Alt+Shift+Esc` 註冊失敗會拒絕開啟。
4. 先把遊戲視窗放前景，再下任務：
   `curl -X POST -H "X-SIRO-Computer-Token: $T" -H 'content-type: application/json' -d '{"goal":"…"}' http://127.0.0.1:8000/v1/computer/run`
5. 看進度：`GET /v1/computer/status`（同 header）；結果含每步動作、預期、結果、畫面是否變化。

## 會自動停下的情況（reason）
`emergency_stop`、`control_disabled`、`executor_offline`、`window_not_allowed`、`blocked_title`／`blocked_process`／`secret_field_focused`、
`stuck_no_visible_change`（連 3 步畫面沒變）、`low_confidence`（<0.6）、`needs_owner`、`decider_stuck`、`outcome_unknown`（不重送）、
`too_many_invalid_decisions`、`step_limit`（40）、`time_limit`（600 秒）、`cloud_screen_not_allowed`。
「done」需附畫面證據，且連續兩次新觀察都判定完成才算。

## 已驗證與未驗證
- 已驗證（自動測試）：閘門／限速／急停鎖存；通道逾時＝unknown；決策迴圈在假桌面上的成功、卡住、越界、阻擋視窗、急停、輸入遺失；
  截圖座標縮放；Electron 端 mock 測試；真 helper 的視窗查詢與拒絕非法動作；真 Electron `desktopCapturer`（1920x1080→1280x720，約 0.8 秒、347KB）。
- 已驗證（真雲端模型、合成畫面）：`scripts/verify_computer_vision.py`，4 例中 3 例過（點 START、有證據的 done、密碼畫面問 owner）；
  「畫面沒反應時不盲目重複」一次過、一次失敗（改用 move 到同座標，信心 0.5，迴圈會因 <0.6 停下）。結果在 `docs/verification/COMPUTER-USE/vision-eval.json`。
- 未驗證：任何真實鍵鼠注入、急停熱鍵實測延遲、真遊戲、反作弊相容、DPI 縮放多螢幕（目前只支援主螢幕）、整條 後端↔桌寵 HTTP 實機串接。
- 已知限制：遊戲內若標題含 login／bank 等字會被擋；只支援主螢幕；每步約 7–10 秒（雲端視覺），不適合即時動作遊戲；
  `core/computer.py` 的 `desktop.*` 能力仍標不可用（舊目錄，未使用）。

## 聊天工具（SIRO 自己決定要不要用）
設了 `SIRO_COMPUTER_TOKEN` 且 candidate profile 時，工具目錄多兩個工具：
- `computer.play(goal)`：effect=computer（R05 唯讀規劃器不會用它）。只在「托盤已開啟」且「桌寵已連線」時才顯示為可用；
  背景執行，立即回傳 started。同時只允許一個 run。
- `computer.status()`：唯讀，回報是否開啟、是否執行中、每步與停止原因。
注意：授權模式為 `full` 時，現有工具審批機制不會逐次詢問；實際把關是 token＋托盤開關＋程序白名單＋截圖同意旗標＋急停熱鍵。
想逐次確認可把授權模式改成需審批（沿用 R02/R04 設定）。

## 實機驗證紀錄（2026-10-29，由 Claude 在 owner 授權下自行執行）
環境：獨立後端（`scripts/computer_use_e2e_backend.py`，port 8777（先前用 8765，與 ESP32 接收器衝突風險，已改））＋獨立 Electron 測試殼（`desktop-win/computer-e2e.js`），不動正在跑的桌寵與主 gateway。
- **Notepad（用我自己的測試檔）**：真實 SendInput 成功。SIRO 看畫面→點進文字區→輸入 `hello siro`→看到結果→連續兩次新觀察確認完成。
  過程抓到並修掉的真問題：
  1. 輸入法（日文 IME／注音）會把字母變成組字，文字被吃掉 → 輸入前切到 US 版面、輸入後還原。
  2. 長輪詢期間後端誤判桌寵離線（輪詢 20 秒、判斷窗口 10 秒）→ 輪詢中視為在線。
  3. 模型自創欄位名 `combo` 造成動作無效 → prompt 列出每種動作的確切欄位，解析器接受 `combo` 別名，格式錯誤自動重試一次。
  4. 全螢幕截圖會把桌面上其他視窗（含私人對話）送給雲端 → 現在只裁出前景視窗再送。
  5. 冷啟動輸入 helper 要約 2.6 秒編譯，首個指令曾逾時變成 unknown → helper 就緒握手、啟用時預熱、輸入逾時 12 秒。
  6. 鍵盤改用硬體掃描碼＋可設按住時間（遊戲才讀得到），新增 `wait` 決策（轉場／黑畫面）與每步「看到什麼」記憶，讓模型能發現自己在原地打轉。
  - 模型自己發現文字打錯（`hello oooo`）並提出全選重打，驗證迴圈確實有效。
- **Undertale（G:\SteamLibrary，日文版，視窗化）**：真實按鍵 Z 能推進開場劇情，SIRO 能讀日文劇情字幕、在黑畫面時等待、在 Logo 畫面嘗試長按。
  **未完成**：開場結束後出現 `UNDERTALE [PRESS Z OR ENTER]` Logo，按 Z／Enter（含長按 1 秒）都沒有進入「為倒下的人類命名」畫面，約 5–6 秒後整段開場自動重播。
  原因未查明（可能是遊戲本身行為、也可能是該畫面讀取的輸入路徑和我們的注入不同）。請 owner 親手在 Logo 畫面按一次 Z，若能進命名畫面，代表是輸入注入的問題，我再查。
- **2048（自製測試遊戲 `tests/fixtures/computer_use/game2048.html`，Edge app 視窗）**：通過。目標「湊出 32」，SIRO 用真實方向鍵 18 步完成，每步記下棋盤內容、合併後確認，最後兩次新觀察都看到 `YOU REACHED 32!`；我另用截圖獨立核對（棋盤左上 32、分數 124、步數 18）。這證明「看畫面→判斷下一步→鍵盤操作→驗證→完成」在真實遊戲型態下可行。
- **Undertale 補充調查**：owner 的存檔存在（`%LOCALAPPDATA%\UNDERTALE\file0`，2024-07-17，未被我動過；**絕對不要讓 SIRO 選 Reset 或存檔**）。在 Logo 畫面分別用掃描碼與虛擬鍵兩種注入、Z／Enter、輕點與長按 600 ms，共 6 種變化，Logo 都不反應（畫面白色比例不變）；但同一種注入在開場劇情中有效。因此原因仍在 Logo 畫面對輸入的讀取方式或遊戲本身，待 owner 手動按一次 Z 對照。
- 驗證後已清理：測試殼、後端、Undertale 都已關閉，截圖已刪。Notepad 內留有我的測試分頁 `siro-test.txt`（未儲存，內容 hello siro），可直接關掉不存檔。
