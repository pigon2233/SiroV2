# Claude 交接入口

日期：2026-10-18（Asia/Taipei）。狀態：**計畫已寫，程式任務尚未認領／開始**。

## 使用者分工

Codex：Live2D 畫面設計及素材／rig／動作資料製作、視覺驗收。
Claude：所有正式程式，包括 runtime、自主活動、情境觀察、活動監測、renderer／宿主接線與 production UI。
Codex 不會同時修改 Claude 的 renderer／host／index.html；Claude 不覆寫 Codex 的資產設計。
請先讀 [README](README.md)、[TASKS](TASKS.md)、[CONTRACTS](CONTRACTS.md)。

## 開始時必做

1. 讀根 AGENTS、STATUS、runbook 與既有 Companion 計畫；fetch 遠端及 open Issues／PRs，
   確認 owner、branch、基線與 dirty 檔案。本計畫從 `3c7ee58de4f53129ed35be5d9877979d7efc586c` 開始。
2. 原 checkout 已見 core/companion.py、core/memory.py、static/index.html 及相關測試的
   未提交修復，另有 T10-OWNER-FIXES evidence。請確認現有 owner／進度，不能 reset、
   stash 或把未驗 dirty code 當作修復完成。
3. 新工作使用自己的獨立 branch/worktree；延續修復則由原 owner 在原任務交付，不另造重複修復。
4. fetch `test/t10-owner-acceptance-20261018`，讀其中
   `docs/evidence/T10-OWNER-ACCEPTANCE-2026-10-18/SUMMARY.md` 及 RESULTS 的後續更正。
   舊取消通過已撤回：刷新後出現「等待完成」、未見新卡、舊語音失敗但新對話正常。
5. 先完成 CP-00 契約接收／source path 對映，再執行 CP-P00 已知問題修復。
   與 Codex 的 V01／V05 可平行，待素材包接收才改 renderer 接線。

## 必須保留

- 現有身份、記憶、情緒、授權／privacy、單 writer、session、取消隔離、原可用聲線與中文輸入。
- Body v1 和既有 API／state／config：本計畫欄位是草案，不能直接破壞升版。
- terminal fence：不能為工具卡改成完成，就放行取消後的舊 tool_result／文字／TTS。
- 對話的通用代理已實際接入，不把既有 computer.execute 說成尚無實作；要補的是可靠整合。
- 模型輸出、網頁指令與桌寵動畫沒有額外執行權；背景研究走同一 runtime 與工具紀錄。

## 建議程式施工序列

CP-P00 → P02 真監測 → P03 介面 → P04 有界自主活動 → P05 情境理解。
P01 動作接線在 V02 就緒後並行；P06 全身生活等 V04。
P04 前 P01／P03 要驗收，I01／I02 才做整體與發布。
這是 dependency 次序，不要求一口氣做完所有卡；一次只做一張 executable task。

整合文件由 Claude 接收後更新 STATUS／DECISIONS／roadmap，引用本計畫與 Codex 的各卡 evidence。
Codex 只寫專屬交接以避免共享文件撞檔。每卡檢查 diff，精確 stage，commit／push／Draft PR，
交接需實際 head SHA、測試與限制；不直推 main、不 force push、未授權不部署。

## 本規劃交付紀錄

- Branch：`plan/companion-visual-autonomy-20261018`；owned paths：`docs/companion-workflow/`。
- 新增 README／TASKS／CONTRACTS／本交接，沒有改 production、部署、共享進度或對方 dirty 檔案。
- GitHub 查詢 open Issues／PRs 皆無結果，但不能視為無本機／外部在途工作。
- 本輪建立 Issue 仍被 integration 403 拒絕；無 Issue URL，也沒有成功共享認領。
- Codex 未發訊息到其他 AI 對話、未建立另一個聊天、未啟動自主工作。
- 文件檢查 PASS：所有本地相對連結有效、16 張卡 ID／owner／詳細卡完整、依賴皆存在且
  無循環，自主執行的修復／監測前置 gate 保持；git diff --check PASS。
- commit／push／Draft PR 結果以本分支實際 Git 歷史及最終交付回覆為準；
  如 PR 仍 403，請有權限的整合者開 PR。
- 同步結果：計畫 commit `e840a26` 已成功推送；建立 Draft PR 同樣回 integration 403。
  目前為 PUSHED／BLOCKED_PR，沒有 PR URL，尚未合併 main，也尚無 Claude 接收回覆。
  取得文件可用 `git fetch origin` 後讀此分支；不要將整份分支直接覆蓋到現有 dirty checkout。
- source／asset／硬體／實作測試本輪未跑；不能把 PLANNED 改 DONE。

## 何時請使用者協助

角色外觀提供具體圖稿後確認；Editor／可編輯 rig 匯出缺環境時說明最小需求。
新程式的真人自然度／語音、WSLg／跨機在已可操作版本上逐項測，不先索取私人資料。
一般工程選擇、可逆設計與已授權範圍內不反覆問許可。
