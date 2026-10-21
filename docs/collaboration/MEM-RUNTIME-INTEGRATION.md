# MEM-RUNTIME-INTEGRATION：記憶基線整合與明確啟用的文字試用

Owner：Codex／本對話；2026-10-22 Asia/Taipei。
Status：PARTIAL / FAILED_VERIFICATION / LOCAL_ONLY / NOT PUSHED。
授權：使用者「實作」，承接 RT／Hermes 記憶接續計畫。
Base main：`89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；前置本機記憶分支
`af89a1c8595631440c0b22b81ccc6e7ba1b29ae3`，尚未遠端整合。
Branch：`codex/memory-runtime-integration-20261022`。
Worktree：`E:/coding/Worktrees/memory-runtime-integration/SiroV2`。

開始前讀 STATUS／runbook／ACCEPTANCE／collaboration、接續計畫及既有契約。
main checkout clean；fetch 成功，origin/main `60af7f1fa2ccf76be63d89b33c90da9590725e0e`。
GitHub issues／pulls 以 per_page=100 查詢第一頁各零筆，無下一頁；沒有遠端認領。
沿本對話既定本機交付／不遠端寫入範圍，以本檔記錄而不建立 Issue／PR，
這與 main 的 GitHub 協作預設不同，不宣稱共享鎖或遠端可讀。

本卡先整合 main 與前置記憶分支；merge-tree 預查僅 CONTRACTS／DECISIONS 有文字衝突。
允許精確衝突解決：`docs/CONTRACTS.md`、`docs/DECISIONS.md`，保留雙方契約與決策；
其餘前置分支與 main 成果只作整合，不重寫、刪測試或整檔選 ours/theirs。
新增實作 owned paths：`src/siro/cli.py`、`src/siro/services/agent/local_memory.py`、
`tests/integration/test_local_memory_runtime.py`、`tests/unit/test_local_memory_profile.py`、
本檔、`docs/verification/MEM-RUNTIME-INTEGRATION/`。
新增契約與決策先記錄於本任務報告，不改共享 STATUS／TASKS／roadmap，由整合者接收。

功能切片：既有 demo 對話流程明確傳 memory profile 才啟用本機 hybrid／relevance 檢索，
預設 offline demo 保持不需模型。組裝沿 MemoryService／CompanionCore，不新增聊天迴圈。
demo 的回答模型仍為 OfflineDemoModel，必須明示，不能冒稱真聊天模型品質驗收。
設定須有本機模型 digest、界限與嚴格欄位檢查；本輪不安裝模型／依賴。
排除 Gateway／UI／活動 producer／正在使用的服務、私人 DB／設定、自動保存／主動提醒。
正式接線與 MEM02 品質 gate 保留，這是可重現試用入口而非完整產品 DONE。

驗收：真 SQLite 新建及 15→18、備份還原／不相容 release 回歸，來源修正刪除失效；
設定錯誤在 DB／HTTP 前拒絕；default zero model calls；profile 啟用沿真 Core 流程、
本機適配器可用 mock HTTP 驗明、失敗無假成功、取消釋鎖／owner guard保持。
模型語意與 L3 分開；相關整合回歸／Ruff／mypy／diff，精確路徑 commit，不 push／merge main／部署。

整合首輪結果：2949 PASS／48 FAIL／19 SKIP，來源前後相同；沒有稱整體 PASS。
必要測試適配新增 owned paths：`tests/integration/test_activity_monitor.py`、
`tests/integration/test_runtime_status_context.py`。前者固定驗 schema15／舊14 reader，
後者解碼新增 data_only observation JSON 後再檢查 runtime status，不移除原斷言意圖。
兩檔在當前 main 已提交、無 dirty，遠端無競爭認領；不改 activity／Gateway／UI 的產品程式。
開發環境隔離補齊限既有 lock/cache：task 專用 WSL ext4 venv、工作區 ignored .venv 指向它；
不重指共用 venv，不下載新依賴，不改使用中的服務／模型。缺 cache 則保留限制。
追加 owned path：`.gitignore`，保留原 directory 規則並排除根目錄的 .venv／target symlink，
避免把 task 專用 ext4 環境指標納入 Git。開始前該檔與 main 相同、沒有 dirty／競爭認領。
trusted worker 僅掛入 workspace/.venv；測試須從該入口執行，不能把外部 ext4 executable
路徑當作 sandbox 內已可見。維持原隔離，不擴大 host mount 或改 worker 權限。

## 交接結果

新增32專項通過；必要適配後87項、workspace入口72項均通過（重疊不加總）。
最終selected1255項：1254 PASS／1 FAIL／0 SKIP，唯一失敗為busy Gateway子程序
未在既定5秒內返回。未改門檻，保持FAILED_VERIFICATION；不宣稱正式接線或產品DONE。
六檔Ruff/format、四檔scoped strict mypy、schema export、四檔scoped secrets均PASS；
全域lint/type仍有診斷，不能宣稱全scripts/check過關。
詳 `docs/verification/MEM-RUNTIME-INTEGRATION/REPORT.md`、三輪receipt與失敗摘要。
runtime驗收後只新增交接／報告／摘要，不再改已驗執行碼。
main在期間另前進，保留89b凍結基線，不擅自納入其他人的新工作；後續整合須另驗。
只暫存本卡精確路徑；完整收尾SHA由git log及最終訊息提供。
