# FIX-004 — session lifecycle repair

2026-10-07；baseline 為已完成 FIX-003 的 UI／測試，加原 Gateway。使用者已授權依三份文件實作。**DONE / VERIFIED（限定本卡）：最終源碼真 UI 跨 TTL、回歸與source回退通過；未部署私人服務。**

## 實作範圍

頁面依 session API 的 expiry 在需要使用時 single-flight 換證，使用單調時間、最多15秒提前量、5秒 bootstrap timeout、3秒失敗冷卻。保留300秒TTL、Origin／loopback／Bearer；只對同來源、固定訊息的401 pre-accept拒絕重試一次。拒絕轉址，保留 STT MIME、Blob／JSON body及取消訊號。其他401／403／500／502／transport outcome unknown均不重送。

控制連線以單一 attempt、owner／epoch、retired fence維護；snapshot 才代表 ready，open 不代表已認證。斷線最多三次自動重連，亦有手動入口；狀態恢復不重播工作或語音。逾時／關頁會釋放 readiness；取消、新輸入及關頁可阻止仍在等待認證／換證的訊息發送。未送出的文字保留為草稿，已有新草稿時不覆寫；已嘗試送出但結果未知不復原成未送狀態。

Gateway 在 issue 時清除過期token、最多保留128個有效token；滿額429，不驅逐仍有效的其他頁面。一般換證不拆正常 control／body。沒有改 Core、provider、工具授權、DB schema、私人設定或聲線。

## 已執行驗證

| 證據 | 結果與界限 |
|---|---|
| session factory 首輪合成反例 | 23 PASS／2 FAIL：Headers實例遺失音訊標頭、`/v1/../body`經正規化越界。當時只有工具輸出，未存完整raw log；修後納入26項factory驗收 |
| `control-before.log` | 首輪10 PASS／3 FAIL：逾時後late snapshot、unload未清ready、ready等待中取消仍POST；其後另兩個FAIL驗換證等待及重疊輸入取消。根因逐一局部修正 |
| `control-after.log` | 中途43 PASS／12 FAIL：抽取舊handler的fixture缺新增retired／submission變數；補stub後轉綠，未鬆綁產品契約 |
| `control-final.log` | 55 PASS，3.73秒；較後補重疊取消反例，由下列最終相鄰回歸覆蓋 |
| `session-final.log` | 39 PASS／2既有warnings，2.40秒；含真 ASGI expired turn／speech在接受工作前401、零effects |
| `regression.log` | 123 PASS／3既有warnings，13.51秒；Gateway／main／terminal、control18、session26、tokens13、frontend、speech cancel、Qwen lifecycle、body isolation、FIX-003 provider completion整合 |
| `full-regression.log`、`full-failures-after.log` | 首輪552 PASS／2 FAIL；一處journal test沿用舊socket擷取字串，更新為實際connectControl邊界；另一處completion-first在尚未cancel前、SQLite transition await觸發2秒timeout，改前置完成fixture等待為有界10秒。取消後原2秒與所有effects／terminal／state斷言保留；cancel本身2秒另有Gateway terminal fence驗收。trace不證明磁碟／鎖／排程根因。兩組61 PASS／3 warnings，20.31秒；獨立唯讀複核無門檻下降 |
| `full-regression-final.log` | 最終整體回歸554 PASS／5 real_provider deselected／3既有warnings，99.87秒。未把未選取真provider tests寫成通過；FIX-003真配置模型樣本另有報告 |
| `mypy.log`、`ruff.log`、`ruff-repo.log`、`format.log` | 199 source files型別檢查PASS、全repo lint PASS、261檔格式PASS；evidence scripts亦明確lint／format PASS。未執行遠端CI、重新安裝依賴或重建未修改的Rust workspace |
| `rollback.json`、`source.patch`、`verify_rollback.py` | 隔離來源reverse／reapply PASS；6個原檔完全恢復、3個新測試移除。基線保留FIX-003，不動私人DB或正在運行的服務。不是部署回滾驗收 |

獨立唯讀複查與重跑：control18＋factory26，共44 PASS，2.79秒；未見剩餘本卡合成測試阻擋。Node synthetic clock／socket、ASGI與真瀏覽器證據分開，不以假時間取代真300秒驗收。

## 真 UI 與交付判定

`verify_ui.py` 使用真 Chromium、真 Uvicorn／Gateway／index.html、真300秒TTL及原生Audio播放；backend只有合成對話事件與150ms靜音WAV。它驗的是頁面、認證、播放生命週期與無重送，不是模型智慧、原聲線聽感或Live2D動作。isolated ephemeral loopback不接觸8026、私人DB、模型或密鑰。

子agent第一次因其socket sandbox拒絕、尚未開server/browser：見 `ui-sandbox-attempt.json`。root第一輪306.743秒PASS／exit0，存 `first-ui-verification.json`／`first-ui-exit.json`；因其間繼續加固取消，沒有用該輪代替最終固定源碼驗收。

最終 `ui-verification.json`／`ui-final.log`：**306.581秒、PASS／進程exit0**。loaded main script／source at-load／at-finish SHA完全相同、頁面JS錯誤0；初始兩個token（控制頁／body各一）、control／body各一連線。TTL後第二輪對話與原生Audio播放／ended成功，只有一次HTTP換證、正常control／body未重建。合成token cache失效後只有401→200一次安全補送、accepted turn與TTS各一次；主動切control後只恢復snapshot，turn／TTS重播0、body owner不變。共3輪合成對話／3次靜音Audio playing／ended均成功；最終browser／body／control／Uvicorn／listener全清理才寫PASS。

實跑命令：`.venv/bin/python -u docs/evidence/FIX-004-2026-10-07/verify_ui.py --chromium /opt/google/chrome/chrome`；`.venv/bin/pytest -q -m 'not real_provider'`；相鄰123項回歸命令列於終端紀錄，完整檔名集合為Gateway／main／terminal、frontend四檔、tokens、Qwen lifecycle、body isolation、provider completion。上述瀏覽器測試是隔離測試服務，沒有重啟正在使用的私人服務。

本卡完成也不解除 FIX-005語音長文完整性／速度、FIX-006情境理解、FIX-002搜尋、桌寵與自主技能gates。沒有部署、私人聊天匯出、真硬體聲音驗收或全產品完成聲明。
