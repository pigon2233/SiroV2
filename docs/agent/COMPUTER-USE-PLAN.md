# SIRO 電腦操控計畫（螢幕讀取＋鍵鼠控制＋感知→決策→行動）

狀態：階段 1–4 程式已完成並以假桌面／mock／合成畫面驗證（LOCAL_ONLY / NOT PUSHED）；階段 5 為 owner 實機驗證，未做。操作與限制見 COMPUTER-USE-RUNBOOK.md。
目的：owner 之後讓 SIRO 玩遊戲來驗證。授權上限已在 R02/R04 存在；本計畫沿用，不另建一套。

## 研究結論（來自本倉庫現況）

- `core/computer.py` 已有 `desktop.window/key/pointer` 能力名，但全為 `available=False`（unsupported）。
  → 實作完成後才翻成可用；風險等級 `normal`，政策預設 DENY/ASK。
- 後端在 WSL，無法從 Linux 側注入 Windows 輸入；桌寵是 Windows Electron（`desktop-win/main.js`），
  已有 `screen` 模組與常駐主程序。→ Windows 原生執行器放在 Electron main（或其旁的 PowerShell/SendInput helper），
  後端經現有本機 loopback＋token 通道送「已通過閘門」的動作。
- R05 `Coordinator` 已提供 plan→verify→report，R06 已有 checkpoint；但 R05 只允許 read 工具。
  → 動作類子任務需新 port（`SubtaskToolPort` 之外的 `ActionPort`），副作用不可自動重送（沿用 R06 unknown 語意）。
- 螢幕屬 Sensitive（SECURITY_PRIVACY §3）：預設 local_only，外送雲端需 owner 對來源/目的地允許；截圖不入記憶。
- 規劃/驗證走雲端（`claude -p --model claude-haiku-5-5`，Pro 登入）；本地 gemma4:e4b 只負責閒聊／fallback。

## 安全底線（階段 1 已實作）

`services/computer_use/safety.py` 的 `ControlGate`，所有輸入動作先過閘才能執行：
- 預設關閉（`SIRO_COMPUTER_CONTROL_ENABLED=1` 或 owner 明確 `enable()` 才開）。
- 急停 `trip()`：鎖存，優先於一切，只有 owner 再次 `enable()` 才解除（hotkey／UI 按鈕接 `trip`，階段 2 接線）。
- 動作白名單：move／click(left,right)／scroll／key／type；其餘（drag、shell、啟動程式）一律拒絕。
- 限速：每秒 5、每分 120。座標限於允許的螢幕範圍。
- 禁組合鍵：Alt+F4、Ctrl+Alt+Del、Win+L/R/X 等。
- 不輸入機密：感知標記為密碼欄、符合金鑰樣式、或等於環境中含 key/token/secret/password 之值，皆拒絕。
- 驗收：`tests/unit/test_computer_use_safety.py` 15 項通過（WSL，ruff 通過）。

## 後續階段（每階段一停）

| 階段 | 內容 | 完成標準 |
|---|---|---|
| 2 | Windows 原生執行器（SendInput）＋全域急停熱鍵＋Gateway 可見開關與狀態；`desktop.*` 能力翻為可用 | 實機：熱鍵 ≤1 次按壓即停；閘門拒絕案例皆 0 次實際輸入 |
| 3 | 感知：視窗標題/前景程序、螢幕截圖（Electron `desktopCapturer`）、遮罩規則（密碼欄、隱私視窗黑名單）；擷取後即丟 | 合成畫面測試；截圖不落盤、不入記憶 |
| 4 | 決策迴圈：感知→（雲端）決策→過閘→執行→重新感知驗證；每步 readback，步數/時間上限，卡住即停回報；接 R05/R06 | 合成環境（假桌面）plan→act→verify 通過；unknown 不重送 |
| 5 | 遊戲驗證（owner 排）：先單機低風險遊戲，僅限前景視窗白名單；延遲與成功率記錄 | 實機報告，含失敗案例 |

風險：誤點擊造成不可逆效果（前景視窗白名單＋每步驗證）；截圖外送（預設不外送）；
迴圈失控（步數／時間／速率上限＋急停）。
