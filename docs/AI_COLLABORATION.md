# SIRO V2：透過 GitHub 協作

本流程讓不同 AI、不同電腦與人工貢獻者有共同可讀的工作紀錄。GitHub Issue／PR
負責認領與交接，Git branch／worktree 隔離檔案；聊天記憶、本機未推送 commit
與單一共享 checkout 都不能代替這兩件事。使用者明確指示優先於本流程。

## 1. 開始前：確認別人在做什麼

1. 讀 AGENTS.md、STATUS、任務規格；檢查本機 status、branch、worktree 與近期 commit。
2. fetch 遠端；讀目前未結 Issue、所有未合併 PR（包含 Draft）與相關 diff。
   查詢要處理完整分頁，不能用第一頁無結果就斷言沒有其他任務。
3. 使用者已指定別的 AI 負責的範圍，即使尚無 Issue，也要視為已占用。
   目前使用者交由 Claude 處理 T10；其他貢獻者不得自行接手或修改其 dirty 檔案。
   這是目前交接資訊，之後以使用者更新及 GitHub 認領紀錄為準。
4. 重用對應 Issue；沒有才建立。先登記下列欄位，再開始編輯。

| 欄位 | 必填內容 |
| --- | --- |
| Task / owner | 任務、實際執行者或 session 代稱；AI 名稱不等於不同 GitHub 帳戶 |
| State / updated | CLAIMED、IN_PROGRESS、BLOCKED、READY_FOR_REVIEW 或 HANDED_OFF；日期與時區 |
| Base / branch | 完整基線 SHA、目標分支、任務分支與獨立工作區 |
| Owned paths | 預計修改的具體檔案／目錄；包含測試與共享文件 |
| Scope / excluded | 要解決的問題、不做的事與不可改區域 |
| Validation / handoff | 驗收、回歸範圍、交接對象或下一動作 |

認領後再重新讀相關 Issue／PR，確認沒有另一個 owner 的重疊路徑。
評論與 assigned 狀態不是原子鎖：兩方同時認領時，先協調並留下明確接收回覆，
不能依自己較新的時間戳判定取得權利。不要只因一段時間無更新就接管；
由原 owner 明確移交或使用者重新指派。

## 2. 實作：每位執行者使用獨立 checkout

- 一任務一分支，例如 `ai/codex/task-id-short-name`。從 fetch 後確認的遠端基線建立
  worktree；若基於未合併工作，明列前置 PR 與 base SHA，不能混入不相關成果。
- 原 checkout 已有使用者或 Claude 的修改時，不搬走、不 stash、不切 branch，
  不把這些檔案偷偷複製進自己的交付分支。使用者明確要求接續時才做有紀錄的移交。
- 修改前核對 owned paths；新增路徑或跨任務依賴時先更新認領並檢查衝突。
  同檔不同段也可能互相影響，不以「不同段」自動取得寫入權。
- 對 STATUS、TASKS、roadmap、DECISIONS、lockfile 等共享文件指定一位整合者。
  若已被占用，將結果寫到 `docs/collaboration/<task-id>.md` 並由 PR 交接；
  此時延後共享 STATUS 更新是明確例外，完成前須由整合者確認納入。
- 不動另一台電腦的部署、服務、私人資料與設定；原先部署授權不自動擴及新部署。

## 3. 驗證與 commit：進度可保存，完成不可虛報

1. 修改後跑 task-specific、相關 unit／integration／regression，文件修改則做對應文件檢查。
   新功能要檢查相鄰既有流程，不只測新 helper。未跑、跳過、模擬與真人驗證分開記錄。
2. 檢查 `git diff` 和 staged diff，明確列檔案加入暫存；禁止廣泛收進他人變更。
3. 每項工作結束前建立 commit；中途被要求停止時，不為湊 commit 繼續開發，
   可將已授權且安全的進度與限制保存為 checkpoint。無修改時不做空 commit。
4. 有未過測試或缺驗收時照樣誠實記錄 PARTIAL／FAILED_VERIFICATION／BLOCKED，
   不因已 commit 或已開 PR 就改為 DONE。不可提交 secret、真錄音、私人對話或無授權資產。

## 4. 推送與 PR：不同電腦必須讀得到

將任務分支推送 GitHub，再建立或更新 Draft PR，連結認領 Issue。
PR 至少包含：問題與結果、owned paths、base/head SHA、驗證命令與結果、
未驗項目、相依 PR、資料／設定影響與回退方式。不可把本機絕對路徑當唯一證據連結；
提供 repo 內相對路徑或 GitHub permalink，確保另一台電腦能取得。

整合前重新 fetch，比對最新目標分支與其他 PR，列出重疊檔案。若需整合，
在自己分支 merge 最新基線，保留雙方修改，重跑受影響的驗證並推送更新。
禁止自行 force push 共享分支、改寫別人的 commit，或整檔選 ours/theirs 當作解法。
對自己的已發布分支也優先追加修正 commit，需重寫時先取得明確授權。

由使用者或被明確授權的整合者決定合併；AI 不自行 approve 自己的 PR、
直推 main 或部署。CI 綠燈不能代替人工／硬體／provider 驗收。
合併後在 Issue 記錄最終 merge SHA 與未解限制，才釋放認領。
移除 worktree 前須確認所有需要的資料已 commit／push 或另外保存；禁止清掉他人工作區。

## 5. 交接與失聯

交接紀錄至少包含 Issue／PR URL、最新已推送 SHA、分支／base、變更檔案、
精確測試結果、未提交／未推送內容、未解問題與下一動作。
接手者先讀此紀錄與實際 diff，再確認 owner 已移交；不能只相信 implementation report。

GitHub 無權限、離線或工具失敗時，立即標示 LOCAL_ONLY／BLOCKED_SYNC，
保留本機 commit，不假稱已認領或已上傳。可做唯讀調查；使用者已明確授權且
與已知 owner 不重疊的範圍，可在獨立 worktree 準備，恢復連線後先補認領檢查再開 PR。
不能因連線失敗就直接改共享 checkout 或 main。

## 6. 規則與技術保護的界線

AGENTS.md、CLAUDE.md、Issue／PR 模板提供所有貢獻者的共同入口，
但不保證任意 AI 會讀取，也不提供跨機原子鎖。本次沒有設定 GitHub Rulesets、
分支保護或額外 CI 阻擋。需要強制保護時，另行核對管理權限、帳戶方案與既有 CI，
設定 PR 必經、必要檢查、禁止 force push／刪除等規則並實測；不可僅憑這份文件宣稱已啟用。
