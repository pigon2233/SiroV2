# 桌寵可操作性修復範圍 — 2026-10-17

對應 T12／桌面體驗卡、EXPERIENCE §3–5、CONTRACTS §4–5 與 native single-owner 補充；沿用 ACCEPTANCE 的 L1／L2／L3 證據界限。使用者回報對話遮住角色、不能縮放、只有「移動」按鈕能拖曳。

## 最小設計

- 保留同一個原生 WebView、DOM、session、renderer 與音訊播放擁有者。打開「聊聊」時，宿主擴展成角色與對話兩個不相交的區域；螢幕過窄改上下排列。關閉對話不重建 renderer、輸入框或事件。
- 同源角色 iframe 可直接按住拖曳，超過 7px 門檻才交由 GTK 原生移動；點一下仍可開對話。保留「移動」作為可見的替代拖曳入口，拖曳結束不誤觸聊天。
- 提供「縮小／還原百分比／放大」，角色請求比例限制 60%–150%，依螢幕工作區收斂實際幾何。角色縮放不縮小對話字體，現有視窗位置盡量保留且不移出工作區。
- 控制列另留在角色下方；宿主只接受 64–320px 的實際控制列高度回報，依有界高度調整視窗，避免小尺寸時控制列覆蓋角色。
- 桌面提供可見的「朗讀：開／關」，只轉送既有 `#voice-output` 的 change；不另建 TTS 或播放管線，不自動開啟麥克風。停止與 Escape 仍呼叫同一個 `#cancel`。

## 安全與不變量

維持精確 loopback URL、同 Origin／iframe source 檢查、短效 session、WebKit sandbox、透明像素穿透、麥克風明確批准。新 native 訊息僅允許固定縮放步進／已驗證螢幕座標／有界控制列高度，不接受執行程式、工具、檔案或模型權限。縮放與對話只改呈現幾何；沒有新增 provider、資料庫、全域事件擁有者或自動部署。既有使用者資料與正在執行的桌寵不由本卡關閉。

## 實作前驗收案例

1. 新反例：打開對話後角色與對話矩形不相交；窄畫面亦保持可見、有界。舊版 fixed 疊卡必須失敗。
2. 直接按角色後移動超過門檻才產生原生拖曳請求；普通點擊、右鍵、跨 Origin、錯 iframe 不取得此路徑；拖曳後不誤開對話。
3. 縮小／還原／放大有可見入口，原生只接受 -1／0／1 步進，重複縮放不超出比例或工作區；對話字體與唯一 renderer 保持。
4. 朗讀只更新既有 checkbox/change；停止與 Escape 在對話、縮放後仍抵達原控制。沒有第二個 socket、Audio 或 iframe。
5. 相鄰原桌面單元／交接測試、靜態檢查；真 Chromium 檢查 DOM 幾何與節點身分；隔離 DBus 的真 GTK/WebKit 檢查尺寸、透明、sandbox 與 side panel 畫面。合成 renderer、真 Haru、實體滑鼠操作分開記錄，未操作的不寫成 PASS。

官方 API 依據：[Gtk.Window.begin_move_drag](https://docs.gtk.org/gtk3/method.Window.begin_move_drag.html)、[Gtk.Window.resize](https://docs.gtk.org/gtk3/method.Window.resize.html)、[WebKit evaluate_javascript](https://webkitgtk.org/reference/webkit2gtk/stable/method.WebView.evaluate_javascript.html)。GTK 的程式化 resize 仍受 widget size request 影響，需真原生驗證；不以合成訊息送達代稱實體滑鼠移動已通過。

此文件保留實作前範圍；最終實作及驗收見 [REPORT](REPORT.md)。實體 Windows 滑鼠拖動仍待人工測試，不以橋接訊息或程式化幾何取代。
