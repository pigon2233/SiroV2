# COLLAB-LOCAL-01 — 本機交付規範與並行盤點

2026-10-20 Asia/Taipei；owner：本次 Codex session。
狀態：DONE（文件範圍）；LOCAL_ONLY／NOT PUSHED。
使用者本輪明確授權修改規範並接續盤點；不推送、不開 PR、不合併。

## 範圍與基線

- Base：137a561c3b5f03c27083eeea2cbd7161b3061d2b（fetch 後 origin/main）。
- Branch：codex/local-only-collaboration-20261020。
- Worktree：E:/coding/股票策略機器學習/SiroV2-local-only-20261020。
- Owned paths：AGENTS.md、CLAUDE.md、docs/AI_COLLABORATION.md、
  .github/pull_request_template.md、docs/companion-workflow/TASKS.md、
  docs/companion-workflow/CLAUDE_HANDOFF.md、本檔。
- 不改 production、renderer、資產、Runtime、DB、lockfile 或使用中服務。
- 原 checkout：claude/vrm-renderer-m1 @ 858f094；有未提交
  renderers/vrm/src/main.js、tests/integration/test_vrm_renderer.py，全部保留。

## 協作檢查及流程偏離

git fetch origin 成功。GitHub REST issues?state=open&per_page=100 與
pulls?state=open&per_page=100 皆回空陣列，無下一頁；不能排除未公開或本機在途工作。
沒有發送 Issue／評論或 PR，沒有遠端認領；使用者指定視覺工作仍視為占用。
本機範圍紀錄於修改後整理，未達舊規則的先登記要求；不追稱已先取得共享鎖。
這次根據使用者明確授權隔離修改規範。docs/STATUS.md 留給共享文件整合者，
本檔代替本輪 STATUS 更新，避免同時覆寫其他工作的進度。

## 候選任務與證據

| 候選 | 已有實作／測試證據（僅讀 source） | 依賴與風險 | 決定 |
| --- | --- | --- | --- |
| 協作規範一致化 | 舊 AGENTS／CLAUDE／流程／PR 模板仍要求 push，與使用者本輪授權矛盾 | 純文件；使用者已指定修改 | 本輪唯一實作 COLLAB-LOCAL-01 |
| 記憶品質驗證 | test_memory_organization.py 有單 owner、搶占、過期視圖與有界清理；另有 ingress/v2/search 測試 | 可獨立測試；須先核對具體缺口與 core owner | 後續候選，不重做記憶系統 |
| doctor 故障診斷 | tests/test_doctor.py 有 secret 不外洩、序列化、服務路徑檢查 | 低 renderer 衝突；先找失敗情境 | 後續候選，不新建監控框架 |
| ESP32 通訊可靠性 | test_esp32_mqtt_probe.py 使用真 broker＋合成 firmware peer；另有 tracker/time/gateway 測試 | broker 整合與硬體驗收分開；不當成真 ESP32 PASS | 後續候選，需確認缺失案例 |
| CP-P02 活動紀錄 | origin/main 已合併 companion-p02；STATUS 有驗證與限制 | UI P03 依賴 V05；不能重新開發紀錄層 | 排除重複實作 |
| CP-V/P 後續卡 | CP-00 接收文件仍為 PARTIAL；卡片定義依賴 CP-00 | 視覺／Runtime owner 與接收未完成 | 不繞過依賴、不接手 |

上述 source 存在不代表本輪測試通過；未驗收任何產品卡或全專案。

## 結果與驗收

規範統一為每項工作本機 commit、禁止直接或間接 push、自動建立／更新 PR 與自行合併；
遠端例外須使用者明確指定操作與分支。保留 fetch／唯讀盤點，採本機交接，
明說本機紀錄非共享鎖、Markdown 不是技術性 push 阻擋。
同步修正 CP-00 卡與 Claude 交接指令；舊歷史推送證據保留並標為歷史。

文件驗證：git diff --check；核對六個規範入口新條款與原 checkout dirty 狀態。
本輪未執行 pytest、scripts/check、真設備或服務測試；純文件修改無產品測試成果。
完整 commit SHA 由最終交付及 git log 提供，避免自引用 commit hash。

## 下一步與回退

由使用者／整合者在方便時檢視此本機分支；沒有同步遠端的待自動執行步驟。
規範目前僅存在本 worktree，其他正在執行的 Agent 不會自動收到更新。
下一個工程候選為獨立記憶品質缺口驗證，須重新核對 owner／依賴與實際失敗案例後認領。
回退為在本分支使用 git revert 對應交付 commit；不改原 checkout 或他人 commit。
