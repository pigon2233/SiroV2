# MEM-GATE-IMPORT：繼續既有記憶整合的 busy Gateway gate

Owner：Codex／本對話，2026-10-22 Asia/Taipei。
Status：本卡 PASS / LOCAL_ONLY / NOT PUSHED；整體記憶產品仍 PARTIAL。
續作本分支既有 PARTIAL，不另建第二 checkout／branch。
Base：`20157b9d9512c24cd2a2c51fc37c74471b7d4ba6`。
Branch：`codex/memory-runtime-integration-20261022`。
Worktree：`E:/coding/Worktrees/memory-runtime-integration/SiroV2`。

讀 STATUS／runbook／既有失敗報告與隱私／驗收規格；本工作區 clean。
fetch 成功，origin/main仍89b；main目前另有已提交desktop工作（盤點d366e6d），不納入。
GitHub issues／pulls各per_page100第一頁零筆、無下一頁；本機記錄不是共享鎖。
沿既定不遠端寫入範圍，不發Issue／PR／評論、不push；不冒稱遠端認領。

最小修復候選：Gateway import tts時載入numpy／soundfile／misaki與jieba，先於main的
exclusive_data_owner；可將三個僅Kokoro render使用的套件延到原to_thread工作邊界。
不改Gateway／owner lease／任何時限／語音算法，不新增owner manager或loader框架。
修改前先以import攔截負例與import-time量測確認，避免把偶發超時說成已知單一根因。

新增精確owned paths：`src/siro/services/audio/tts.py`、
`tests/integration/test_tts_import_boundary.py`、本檔、`docs/verification/MEM-GATE-IMPORT/`。
兩個Python檔在main與本基線相同、無dirty或競爭認領，STATUS未列它們的進行中owner；
既有audio GPU／串流／T10 UI工作不接手。本次只改同一語音實作的import時點。
共享STATUS／DECISIONS／CONTRACTS由整合owner更新，本卡契約與交接留此專屬文件。

契約：pure helpers／建構／busy拒絕不載入上述三套件；第一次owned render才載入，
仍在原worker thread，維持G2P／voice／model快取、參數、輸出、例外型別與取消join。
新增阻止三套件的因果負例先紅再綠；mock音訊不當真聲音品質。
驗收：原5秒busy Gateway真子程序測試不改、tts邊界／相關語音／memory/owner整合回歸、
scoped lint/type、source穩定receipt；不以較長probe、放寬timeout或重跑挑綠解除gate。
不啟動私人服務、不下載模型／依賴、不改DB／GPU／音訊設定。每次工作本機commit。

結果：僅延後三個套件的 import 至原 render worker；負例先紅（三失敗）再綠，
邊界八項通過；原五秒真 Gateway 子程序測試未修改且在最終回歸通過。
最終選定1263 passed / 0 failed / 0 skipped，source前後一致。
詳細命令、限制與後續見 `docs/verification/MEM-GATE-IMPORT/REPORT.md`。
未更新共享STATUS／DECISIONS：依檔案owner規則交整合者處理；未推送、未合併、未部署。
