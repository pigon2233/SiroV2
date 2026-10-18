# D68／T12：桌寵透明命中分析

2026-10-18。限定修復 LOCAL_VERIFIED，整體桌寵／WSLg真人驗收未完成。

c1727e5把診斷改為持續保存pet.png／chat.png；原mask path另每3秒寫alpha.png。desktop/host.js改用Gdk.pixbuf_get_from_surface直接讀自有Cairo snapshot的像素，不落盤PNG；保留inputMask、alpha與native-state metadata。未讀取或刪除歷史影像。

新 test_desktop_snapshot_privacy.py 執行實際updateShape：聊天開關／報告開關各120callbacks、async聊天交錯、snapshot／pixel-conversion失敗與恢復、pending／hidden／loading／close。原版7 FAIL／1 PASS，修復8 PASS。focused69 PASS；較廣桌寵／前端／Whisper／B profile／HTTP cancel／Ollama共493 PASS（30.32s），不同套件有重疊不得相加。

本目錄 verify_native_mask.mjs 使用真Gtk3／WebKit4.1／Gdk，sandbox保持啟用；96x72合成offscreen畫面，原PNG decoder與記憶體路徑mask一致，實際production updateShape輸出有效input regions且未建立PNG。只有驗證器保存一份已知合成圖做原路徑比較，隨即刪除。OffscreenWindow有兩項Gdk-WARNING與get_origin CRITICAL，原log保留；不是零native warning或真桌面互動PASS。

原本啟動的隔離Python3.12 scripts/check中止於MQTT階段，1212 PASS後KeyboardInterrupt／exit2；完整gate NOT COMPLETED，不冒稱PASS。使用者後來要求新增功能後才驗證，本輪續做T10記憶搜尋，見其證據。

額外先前CUA實際任務流程：main/Core/SQLite/Rust，proposed零read→重啟零read→明確批准一次read且來源正確→第二proposed→再重啟零重播。三輪helper已清理owned processes/temp；renderer為合成placeholder，不代證真Live2D或語音。私有log留在忽略目錄.siro-data/verification/T12-SNAPSHOT-20261018。

回退只撤desktop/host.js本卡diff，保留最新資料與其他使用者提交；會恢復原自動PNG診斷行為。D68無新依賴，Node syntax／Ruff／mypy相關測試通過；未部署、未改B聲線／Whisper／IME／WSL入口。來源API：GTK3 Gdk.pixbuf_get_from_surface及WebKitGTK get_snapshot_finish官方文件。
