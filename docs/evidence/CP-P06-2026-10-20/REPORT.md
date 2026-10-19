# CP-P06：全身桌面生活（2026-10-20）

**結果：PARTIAL。** 走路（轉身→起步→走→停→轉回）已接上桌寵視窗移動，含工作區邊界、被叫住、拖曳、
聊天、版面改變、最小化時的收尾；renderer 與頁面橋接、步速數學都有自動測試。**還沒在真的 GTK 桌寵視窗上跑過**
（使用中的 SIRO 沒有重啟，不能另開第二個 host：同一個 application id 會接管使用中的視窗），所以不標 DONE。

- Branch：`claude/vrm-renderer-m1`（本機，未推送）。分工：本卡＝desktop／renderer／presentation static；
  動作片段（V04）由另一個 Claude 對話負責，本卡只使用 pack 裡的 `walk`、`walk_start`、`walk_stop`、`turn_step`。
- Core 的 body 協定不變。新增的訊息只在 renderer ⇄ 頁面 ⇄ 原生 host 之間。

## 做了什麼

| 部分 | 檔案 | 內容 |
| --- | --- | --- |
| 步速數學 | `desktop/wander.mjs` | 起步／停步速度曲線與 walk_start／walk_stop 的步幅混合曲線相同（4u³／1−(2−2u)³/2），各走半個 ramp；中途停下從當下速度再走一個 ramp；工作區內可走距離（離邊 8 px；方向 0 選空間大的一邊） |
| 原生視窗 | `desktop/host.js` | `desktop.walk`（驗證 id、方向、距離 ≤4096 px、速度 10–2000 px/s、ramp 0.2–5 s、轉身前導 0–5 s）→ 依計畫每 16 ms 移動視窗並夾在工作區內；`desktop.walk.stop` 從當下速度停下；拖曳、聊天、版面、縮放、最小化／unmap／withdrawn、關閉都先停住；狀態寫入 native-state.json |
| 頁面橋接 | `src/siro/services/presentation/static/desktop.js` | 只轉送角色 iframe、同源、`v:1` 且欄位合法的請求；聊天開著時直接拒絕；host 回報只轉送合法狀態（started／stopping／ended／refused） |
| renderer | `renderers/vrm/src/main.js` | 只在桌寵模式：向 host 要空間 → `turn_step` 轉 90° → `walk_start` → `walk` → `walk_stop` → `turn_step` 轉回；片段與位移同速（1.26 m/s × 0.7，px/m＝窗格高度／畫面高度）；側身時把步伐中心移回窗格中央；說話、Core 訊息、點擊會叫住她；拖曳交給 dangle；host 一秒內沒回應就不走並取消遲到的開始；右鍵選單「散步」與閒置時偶爾散步 |

## 驗收對照

| 驗收要求 | 狀態 | 證據 |
| --- | --- | --- |
| 走→停→（坐→起身）→被叫住→恢復連貫 | 自動測試 PASS | `test_desktop_stroll_turns_walks_with_the_window_and_stops_when_called`：轉身、起步、走、停、轉回、回 idle；走到一半點擊→送出 stop、立刻 walk_stop、回 idle；之後可再散步。坐下與散步互斥（保持狀態中不開始散步，散步中不開始坐下），兩者結束後都回 idle |
| 腳步與位移一致 | 數學 PASS；真視窗未驗 | `test_walk_travel_follows_the_stride_curve_and_stays_in_the_work_area`：曲線面積＝0.5、位置連續不倒退、速度不超過步速、終點精確、停步距離正確。速度 1.26 m/s 取自 pack.json；px/m 由 renderer 依目前取景換算 |
| 不出畫面 | 測試 PASS＋實測 | 工作區夾限（host 每步再夾一次）；用 owner 模型、360×640 窗格整段走路取樣，左右最少 11／22 px，沒有碰到邊 |
| 不搶輸入焦點 | 設計上 | 走路只用 `window.move`，不 present／不改 accept-focus（桌寵預設 accept_focus=false） |
| 不攔住別的程式 | 沿用 | 透明區域不收輸入（既有 input mask）；走完立即重算 mask（`queueShape`） |
| 拖曳 | 測試 PASS | 原生拖曳開始前先停住走路；renderer 改播 dangle、轉回正面 |
| 鎖屏 | 部分 | 只處理 GTK 會發出的 iconified／withdrawn／unmap；WSLg／各桌面的鎖屏是否送這些事件未驗 |
| 全螢幕 | 未處理 | 目前偵測不到別的程式全螢幕；桌寵仍 keep_above。列為限制 |
| 螢幕移除 | 設計上 | monitors-changed → applyLayout 先停走路，再把視窗夾回新的工作區（既有行為） |
| 多螢幕／DPI 分平台驗 | 未驗 | 只在目前所在螢幕的工作區內走；跨螢幕不走；DPI 未分平台測 |

## 測試

- `tests/integration/test_desktop_host.py`：新增步速／工作區數學、host 訊息驗證與「先停再接管」的位置檢查（2 項）。
- `tests/integration/test_desktop_web.py`：新增頁面橋接（合法轉送、不合法丟棄、跨源丟棄、聊天開著拒絕、host 回報格式）。
- `tests/integration/test_vrm_renderer.py`：新增散步完整流程、被叫住、被拒、沒有 host。
- 相關集合（renderer、motions、desktop web／host、mouth sync、speech queue）：80 PASS；散步測試連跑 4 次穩定。
- 實際模型（headless Chromium＋swiftshader，假 host 回覆）：轉身 facing≈1.57 rad、walk 時腳步在窗格內、結束 facing 回 0。

## 未做／限制

- **真桌寵視窗未跑**：需要 owner 重啟 SIRO 後實際看散步（右鍵「散步」）與拖曳、聊天打開時是否停住。
- 全螢幕偵測、鎖屏事件、多螢幕跨越、DPI 縮放未驗／未做。
- 走路時頭與眼睛朝前方；途中不看使用者。
- 回退：右鍵選單與閒置散步都只在桌寵模式；拿掉 `canStroll()` 的條件或刪除 `walk` 片段即停用，視窗回到原本只靠拖曳移動。
