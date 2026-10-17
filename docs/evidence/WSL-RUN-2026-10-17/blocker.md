# WSL 新資料目錄的5秒readiness失敗

狀態：FAILED_VERIFICATION；根因UNKNOWN，不等於整個gateway無法執行。按SOL_RUNBOOK同症狀三次停止重測／擴大重構。另有模型／角色素材缺失，與本失敗分開。

## 重現

在本機WSL wrapper執行 `pytest -q tests/integration/test_operational_cli.py::test_t34_start_stop_health_and_pid_cleanup`。原測試建立新temporary data，執行scripts/start --demo，最多50次／每次sleep0.1s，HTTP timeout0.2s。未修改原門檻。

## 已試與證據

1. 修正CRLF後74案例：73PASS／此例FAIL。
2. 隔離operational與launcher：14PASS／此例FAIL。
3. 直接執行同一函式，僅改被丟棄的stdout/stderr為capture：5.402s仍FAIL，capture空。helper捕獲exception後exit0不算PASS。

前兩輪合成test目錄沒有logs/siro.log，data/siro.db為4096bytes；未改讀取私人DB。這不足以證明SQLite鎖、migration或硬碟是根因。

獨立真browser probe在新temporary data4.084s ready200，頁面送收離線合成訊息成功，stop後無殘留。單次成功不抵銷測試失敗，也不構成SLO達成。

## 已排除／尚未證明

- 初輪CRLF可直接重現且已修，之後此症狀仍存在。
- 不是尚未設定真provider才拒絕demo；--demo是原本明確離線路徑。
- 未見provider連線或JS錯誤證據；未以更長等待或更換mock當作原測試通過。
- WSL mount效能／排程、DB初始化／migrations耗時、測試與probe的環境差異均未定位。
- 靜態檢閱確認：probe計時前先跑launcher缺模型檢查，與原test直接啟動demo的順序不同，且共用Python cache；此差異未證明根因，4.084s不能列為cold量測。原test保留UV／Python環境。DB初始化早於logging handler；WAL下4096B主DB不代表schema沒寫入。

## 下一個最小調查

用隔離新資料與相同環境、記錄程序／import／DB初始化各階段monotonic時間，保留原5秒gate與server stderr；在原source及Linux內部source的相同版本做對照，先證明耗時來源再提出局部修復。無需私人資料或使用者憑證；本輪不擴重構或改門檻。
