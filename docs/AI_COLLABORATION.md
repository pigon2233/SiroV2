# SIRO V2 協作流程

使用者明確指示優先。2026-10-20 起預設採本機交付：每項工作必須 commit，
不得 push、建立／更新遠端 PR、自行合併、發布或部署。只有使用者另外明確授權
指定遠端操作及分支，才能執行；「完成全部任務」不構成推送授權。

## 開始前：盤點與認領

讀 AGENTS.md、STATUS、runbook、任務卡與引用規格；檢查 dirty 狀態、branch、
worktree、近期 commit。允許 fetch 與唯讀查詢 GitHub 未結 Issues、所有未合併 PR
及其 diff，處理完整分頁。使用者指定給其他 Agent 的範圍，即使未公開認領仍視為占用。

預設不寫入 GitHub Issue／評論；在 docs/collaboration/<task-id>.md 記錄：
Task、owner/session、時間與時區、狀態、完整 base SHA、分支、worktree、精確 owned paths、
排除範圍、依賴、驗收及交接。開始修改前再查一次遠端與本機範圍。
本機紀錄不是跨機共享鎖；重疊範圍須由原 owner 移交或使用者明確指派，不能搶寫。
無法查詢 GitHub 時明列 UNKNOWN／LOCAL_ONLY，不假稱成功遠端認領。

## 隔離與檔案所有權

一任務一分支一獨立 worktree；預設使用 codex/<task> 分支，記錄已核對的基線。
不在使用者 dirty checkout 切分支、stash、清理、覆蓋或搬走他人的成果。
不直接修改 main/master 或其他 Agent 的分支。

STATUS、TASKS、roadmap、DECISIONS、lockfile 等共享檔也需要 owner。
未取得共享文件寫入權，先寫本任務交接，由整合者之後更新；明列延後原因。
新增修改路徑前再核對衝突。不同分支或同檔不同段均不自動代表安全。
不改使用中服務、另一台電腦或私人資料；部署授權需另外確認。

## 驗證與本機 commit

依變更執行必要 unit／contract／integration／regression；文件改動執行文件一致性檢查。
mock、真整合、人工硬體與未執行項目分別記錄，不放寬門檻或用舊報告當本輪結果。
檢查 diff 與 staged diff，明確指定 git add 路徑，禁止 git add . 或 git add -A。
每項工作結束前保存本機 commit；訊息含 Task ID 與摘要，交付完整 SHA。
未通過驗收可保存 WIP／PARTIAL／FAILED_VERIFICATION checkpoint，不標 DONE。
沒有變更不建立空 commit；不提交 secret、私人對話、原始錄音或無授權資產。

## 遠端限制與交接

禁止 git push（包含 --force、--all、--mirror），也不得透過 IDE、API、GitHub CLI、
CI/CD 等間接推送。禁止自動建立／更新遠端 PR、自行合併或同步遠端分支。
本機 commit 不表示 GitHub 可讀。預設交接狀態為 LOCAL_ONLY／NOT PUSHED。
既有 Issue／PR 可唯讀參考；模板僅供使用者另行授權後使用，不授權送出。

交接包含 Task 狀態、分支／worktree、base／完整 commit SHA、檔案清單、測試命令與
實際結果、未驗項目、限制、下一步、回退方法、dirty 狀態及 NOT PUSHED。
使用者決定何時推送與整合；未收到具體授權，不把遠端同步當成必要補做步驟。

禁止 reset --hard、clean -fd、整檔 ours/theirs 或刪除他人測試來消除衝突；
不 amend 他人 commit。需整合時先核對雙方 diff／證據並取得授權，保留雙方意圖。
worktree 清理前確認必要內容已 commit 或另外保存；不能因未 push 就刪除成果。

## 規則與技術保護

Markdown 與模板不是原子鎖、Git hook、CI 或 branch protection。
本規範不宣稱已設定技術性 push 阻擋；需另行授權並實測才能如此宣稱。
