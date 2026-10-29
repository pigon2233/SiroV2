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
  Gateway 與聊天工具目錄尚未接 `desktop.*`（`core/computer.py` 仍標不可用），現階段入口是上述 HTTP。
