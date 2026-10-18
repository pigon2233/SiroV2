# AI GitHub 協作規則交接（2026-10-18 Asia/Taipei）

- Owner：Codex；使用者要求讀 AGENTS.md，建立各 AI 透過 GitHub 協作、避免撞檔的規則。
- Base：`bd63f2809762da35035ea0a69c8787fff633cc04`（fetch 後 origin/main）。
- Branch：`docs/ai-github-collaboration-20261018`；獨立 worktree，未搬移原 checkout 的 dirty 工作。
- 範圍：AGENTS.md、CLAUDE.md、docs/AI_COLLABORATION.md、本交接、Issue／PR 模板。
  不改 T10、production、desktop、共用 STATUS／TASKS／roadmap／DECISIONS。
- 變更：開始前認領與重查競爭範圍、一任務一分支一工作區、共享文件 owner、
  精確暫存與每次交付 commit、推送／Draft PR、衝突處理、離線與權限不足時的誠實降級。
- 本次例外：GitHub 開放 Issue／PR 查詢皆無結果；建立 Issue 回覆 403
  `Resource not accessible by integration`。沒有成功取得共享認領；僅在使用者明確授權、
  已知不重疊的文件範圍隔離準備。T10 仍交給 Claude。
- 驗證：Python／PyYAML 檢查 Markdown 本地連結、Claude 入口、Issue form YAML 語法、
  五個唯一且必填欄位 PASS；`git diff --check` PASS。交付前再核對 staged paths。
- 未驗：GitHub Issue form 網頁提交、各 AI 實際遵守、跨機認領競態；沒有設定或宣稱
  Rulesets／branch protection／新 CI gate。文件修改不跑 runtime suite，不宣稱產品回歸 PASS。
- 共享 STATUS 未更新：避免與 Claude／現有未提交文件衝突，請整合者納入本交接。
- 回退：在整合分支 revert 本任務 commit；此任務只新增文件／模板與追加 AGENTS 規則，
  無資料、設定、public API 或 runtime 格式變更。
- 交接與同步：最終 SHA 與遠端／PR 結果以本分支 Git 歷史及交付回覆為準，
  不在同一 commit 內放自我引用 SHA。未獲授權不合併、不部署。
