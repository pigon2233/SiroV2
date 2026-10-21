# SIRO 2 執行規則

## GitHub 多 AI 協作（開始修改前必讀）

適用 Codex、Claude 與其他 AI／人工貢獻者。完整流程見
[`docs/AI_COLLABORATION.md`](docs/AI_COLLABORATION.md)。使用者當前明確指示優先；
偏離流程須在交接中寫明原因，不能假稱已完成認領、推送或驗證。

- **先認領，再修改**：讀 GitHub 未結 Issues、未合併 PR、最新遠端提交及本機 dirty 狀態。
  在本機 docs/collaboration/<task-id>.md 記錄任務、執行者、分支、base SHA、允許修改的路徑與驗收；
  再查一次有無競爭認領。本機紀錄與 GitHub 評論都不是原子鎖；範圍重疊須先取得交接，不能搶寫。
- **一任務一分支一工作區**：從已確認的基線建立獨立 branch/worktree，禁止多個 AI
  同時在同一 checkout 寫入。使用者的 dirty checkout 不切分支、不 stash、不清理。
- **檔案也要分工**：`STATUS.md`、`TASKS.md`、roadmap、lockfile 等共享檔同樣需要 owner；
  不同任務碰同檔時先拆範圍或序列整合。未取得共享文件寫入權時，先寫本任務專屬交接文件，
  以本機交接文件交給整合者更新共享狀態，不自行覆寫。
- **每次工作都留 commit**：結束前把自己已完成的修改或可接續成果與真實驗證狀態 commit；
  明確指定暫存路徑，不使用 `git add .`／`git add -A` 收進別人的修改。
  commit 不代表 DONE；未過驗收仍標 PARTIAL／FAILED_VERIFICATION。
- **必須 commit、不得 push**：所有成果保留本機，交接記錄完整 commit SHA、測試、限制、
  下一步及 LOCAL_ONLY／NOT PUSHED。禁止 git push（含 force/all/mirror）、IDE／CLI／API／CI
  間接推送、自動建立或更新遠端 PR、自行合併、發布或部署。只有使用者另行明確授權
  指定操作與分支時才可執行；一般「完成全部任務」不代表遠端操作授權。
- **衝突保留雙方意圖**：禁止用 reset/clean、整檔 ours/theirs 或刪掉他人測試來消除衝突；
  先核對雙方 diff 與任務證據，在自己的整合分支處理並重跑相關回歸。
- **無法連 GitHub 就降級**：說明權限／連線阻礙，不宣稱成功認領；可繼續唯讀調查或使用者
  明確授權且範圍不重疊的隔離準備，不能把離線紀錄當共享鎖。

本文件與模板是協作規則，不是自動鎖或 CI／branch protection；實際保護設定須另驗。

## 先讀與續作

1. 讀 `docs/STATUS.md`、`docs/SOL_RUNBOOK.md`、目前任務卡及其引用的契約、體驗、安全與驗收規格。
2. 用 `git status --short` 確認工作區，保留使用者與其他工作留下的變更。
3. 一次處理一張已滿足依賴的任務卡；需要拆分則記錄子任務，不擅自擴充功能。
4. 本文件不指定或切換模型。使用者可選 Sol 實作；不需要其他模型才能推進。

## 架構底線

- Core 不引用 UI、MQTT、具體 provider 或 OS driver 內部實作。
- Identity、Memory 與 LLM 分離；World State 的觀測有來源、時間與有效期。
- Gateway 只驗證、授權連線、轉譯、佇列與傳輸；業務判斷留在 Core。
- 每條連線一個 writer。控制、媒體、設備通道分流且佇列有上限。
- blocking I/O、模型推論、第三方技能不得直接卡住 Core event loop。
- 取消必須傳遞到 LLM、TTS、播放器、排隊工具；過期 turn 輸出不得復活。
- 權限由 Policy + Runtime 執行；模型輸出與設備資料不能替自己授權。
- 有副作用的操作不能因 timeout 不明而直接重送；先查結果或標示 unknown。
- Replay 不執行真實副作用。Memory 寫入需有來源與可撤銷版本。
- 不把舊 Bridge 整個搬入；移植能力時先寫契約測試。

## 交付要求

- 實作任務必須有可重現驗收證據；mock、真實整合、人工硬體測試分開記錄。
- 不將未執行的命令寫成通過，不將跳過測試寫成完成。
- 文件中的數值是設計目標，非已量測成果。更改門檻需記錄原因及影響。
- 新增依賴前核實官方介面、版本與授權，更新 lockfile；不要猜 API。
- 完成後更新 `docs/STATUS.md`：修改內容、命令與結果、限制、下一任務。
- 跨契約變更先更新 `docs/DECISIONS.md` 與受影響測試，再改實作。
- 不把密鑰、原始錄音、私人對話資料寫入 Git；測試使用合成資料。
- 依 `docs/EXPERIENCE.md` 交付使用者可理解的狀態與流程；開發 log 不能取代產品入口。
- 依 `docs/SECURITY_PRIVACY.md` 處理資料分類、外送、保存/刪除、secret、kill switches 與發布阻擋項。
- 發布、自我更新與設備控制依使用者既有授權範圍執行，不因計劃描述就假定已取得外部權限。

## 完成判定

遵循 `docs/ACCEPTANCE.md`。只做出聊天畫面不等於專案完成；研究項目未進入產品也不能偽稱其已實現。缺外部條件時清楚列出阻礙，繼續其他已可執行的任務。
