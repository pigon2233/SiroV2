# MEM-RT-HERMES-PLAN：RT 與 Hermes 借鏡納入記憶計畫

Owner：Codex／本對話；2026-10-21 Asia/Taipei。
狀態：DONE（文件補入）/ PLANNED（新增能力）/ LOCAL_ONLY / NOT PUSHED。
使用者授權：「好啊 那都補進」，承接上一輪補入後續實作計畫的提議。
本卡交付計畫與驗收條件，不把文字新增當成能力實作或正式啟用授權。

Base：`b57c7d28e764ba4556adfb76d6324dcd9291c9b3`。
Worktree：`E:/coding/Worktrees/memory-rt-hermes-plan/SiroV2`。
Branch：`codex/memory-rt-hermes-plan-20261021`。

開始前：讀 collaboration、STATUS、runbook、記憶計畫、MEM03C 契約及驗收／隱私要求。
fetch 成功；origin/main 為 `60af7f1fa2ccf76be63d89b33c90da9590725e0e`。
GitHub issues、pulls 各 per_page=100 首頁為零筆，無下一頁；沒有遠端評論認領。
第二次查詢確認零筆，並核對 owned paths 無 dirty／競爭變更。
本機認領不是共享鎖。

精確 owned paths：本檔、`docs/memory-evolution/PLAN.md`、
`docs/memory-evolution/RT-HERMES-INTEGRATION.md`。
PLAN 是本對話原有記憶分支文件，origin/main 尚無此路徑；僅更新本機後續計畫。
排除：共享 STATUS／TASKS／DECISIONS／RT roadmap、產品程式、測試、依賴、私人 DB、
正在運行的服務、其他 owner 的 Gateway／UI／活動修改。共享進度由整合者按本交接更新。
舊記憶工作區中使用者的 MEM04 report dirty 保留，本工作區不攜入。

驗收：相對連結存在、RT／MEM 狀態不矛盾、Hermes 現行參考與既有固定版本比較分開、
每個新增工作切片有依賴／邊界／驗收／回退；git diff 與 staged diff --check。
文件任務不執行模型推論或產品測試，不沿用舊測試數作本卡 PASS。
只提交上述路徑、本機 commit，不 push／PR／merge／部署。

## 收尾與交接

實際產出：PLAN 更新目前 MEM03A/B/C、MEM04/04B 的限定狀態並連到接續文件；
RT-HERMES-INTEGRATION 列既有 RT／RI 對照、固定 Hermes 比較與現行參考的區別、
分層載入／跨 session 查找、成本評測、審核保存、retention、RT015 背景控制與
T30 技能載入的依賴、驗收、回退及整合順序。Codebase Memory 仍限開發工具。

驗證：PowerShell 逐一解析三檔 Markdown 本地連結，15/15 路徑存在；
必要 RT／MEM、啟用狀態、品質 gate、prefix cache／Codebase Memory 與驗收回退欄位檢查 PASS。
人工對照本輪來源及前述報告，歷史測試數明示非本卡新跑結果；git diff --check PASS。
未執行模型、pytest、服務、硬體或真人測試；沒有新增依賴或變更產品行為。
最終 staged diff 與精確路徑在 commit 前再查，完整 commit SHA 由 git log 及交接訊息提供。

共享 STATUS／TASKS／DECISIONS／RT roadmap 由整合 owner 按此文件更新；本卡沒有寫入。
回退只撤本卡三份文件的變更，保留所有既有實作、DB、來源與其他 owner 成果。
下一步是計畫第一項 main／記憶分支／schema 差異與 owner 範圍盤點，非部署或自動啟用。
提交後本工作區應為乾淨；原記憶工作區的使用者 report dirty 與 main 的其他修改均不動。
