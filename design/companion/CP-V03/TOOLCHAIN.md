# Cubism 工具鏈確認／匯出往返 gate

2026-10-19 Asia/Taipei。**PARTIAL：Wine 已成功啟動 Editor；工程編輯／匯出往返尚未驗收。**

使用者確認只有 Linux，並明確授權嘗試 Wine。已在獨立 prefix 安裝官方 Windows Cubism 5.2.03；主視窗與 OpenGL 4.6 初始化有證據，見 [Wine 實測](wine-2026-10-19/README.md)。這條路徑可繼續測試，不能再把「沒有 Windows／macOS 主機」單獨當作無法嘗試的理由；亦不將相容層啟動等同官方 Linux 支援或完整往返成功。

## 已取得的證據

- 本次執行主機 uname／platform.system 均為 Linux。
- 主 checkout 的 SDK／Haru runtime 已由 V01／V02 在 Linux Web renderer 載入；這是播放工具鏈，不是模型製作工具鏈。
- 在專案樹查找 *.cmo3／*.can3／*.psd／Cubism executable 未找到；查既有 Wine Program Files 的兩層目錄亦未找到 Cubism。
- 本機有 wine 指令，但沒有已驗 Editor 安裝／GPU／授權／PSD 匯入證據；不把 Wine 存在當作 Editor 可用。
- /mnt/c、/mnt/d、/mnt/e 在本輪未取得可用 Editor；不代表使用者沒有另一台 Windows 電腦。
- 前輪未安裝 Editor；2026-10-19 已透過 Wine 安裝並啟動，尚未啟用 PRO／試用或付費。

官方列 Editor 支援 Windows 與 macOS；本機 Linux renderer 能播放不代表能產出可編輯 rig。
[官方系統需求，2026-10-18 核對](https://www.live2d.com/cubism/download/spec/)

## 檔案與來源責任

可編輯模型工程為 cmo3、動畫工程為 can3；runtime moc3／model3.json／texture 等由 Editor 匯出。
不能把平面圖或手寫 motion JSON 當成 cmo3，也不假定能把現有 moc3 無損反編回模型工程。
[官方檔案類型](https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/)
[官方 runtime 匯出](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)

PSD 的 RGB／8bit 與 sRGB、命名與合層處理由素材製作者確認；Editor 匯入後再檢查顏色、alpha 與 draw order。
[官方 PSD 規格](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/)

## 最小往返實驗（未執行）

先做與角色外觀無關的小型測試件，避免花完整角色成本才發現工具不通：

1. 確認主機 OS／Editor 精確版本與 FREE／PRO 可用功能、GPU、實際 operator；不預先指定必須買 PRO。
2. 以兩個有重疊的自有圖形層建立 RGB8 PSD；匯入、調整一個 mesh／deformer，保存 test.cmo3。
3. 設一個可見參數與短動畫，保存 test.can3；關閉後重新開兩個工程並實際改一個 key。
4. 製作 atlas，匯出 test.moc3、model3.json、texture 及 motion3；匯出格式選已測目標 renderer 可讀版本，不能僅依編輯器號碼推斷相容。
5. 在隔離 renderer 解析、載入並播放，錄影；核對 source／artifact hash、參數、alpha、draw order 與 loop／中斷。
6. 在工程改同一 key 再匯出；確認 renderer 可看到不同結果。保留兩版工程／執行包與 hash。

驗收不是只看匯出檔存在，而是「重開可編輯→修改→再匯出→真播放」；
目前僅安裝／啟動有證據，工程往返各步仍 PENDING，不借用 V02 的 Haru motion 解析結果冒充本實驗成功。

## 哪些可自動，哪些仍需實際工具

| 操作 | 本輪能力 |
| --- | --- |
| 概念圖與規格、CSV、來源及 hash | 已完成 |
| 曲線資料檢查、既有 Web renderer 播放 | V01／V02 限定能力，未驗新角色 |
| PSD 隱藏補圖、關節分件與精稿 | 外觀確認後才製作；本輪無分層 PSD |
| Cubism mesh／deformer／atlas／export | 需要可操作 Editor 主機與工具實測，未完成 |
| 正式 loader／renderer 工具接線 | Claude 負責；Codex 提供資料與驗收，不雙寫程式 |
| 外觀確認與自然度評估 | owner 看具體圖稿後確認，不以自動測試代替 |

下一步：在已開啟的 Editor 選擇 FREE 模式，執行兩層測試工程的匯入、保存重開、匯出與真 renderer 播放；再修改並重做一次。Wine 版本與啟動已確認，後續仍需實測。
