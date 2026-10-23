# MEM02-CONTEXT-QUALITY

2026-10-22 Asia/Taipei；Codex本對話；FAILED_VERIFICATION / CANDIDATE_REVERTED /
LOCAL_ONLY / NOT PUSHED。新fixture的L1邊界驗證通過，不代表模型品質通過。
Base f85c7115fd03dabe00f63f9469add8966c69338e；branch codex/memory-context-quality-20261022。
獨立worktree E:/coding/Worktrees/memory-context-quality/SiroV2。
讀STATUS/runbook/既有MEM02/body review報告與隱私驗收；fetch成功，origin/main89b80fb。
main21f630c clean，桌寵工作保留；公開open issues/pulls各100筆第一頁零筆、無下一頁。
依既有使用者本機交付指示不發遠端評論／PR／push，本卡不是共享鎖。

Owned paths：src/siro/core/context.py、src/siro/core/memory.py、
tests/integration/test_context_understanding.py、tests/fixtures/context_quality_holdout.json、
docs/verification/MEM02-CONTEXT-QUALITY/、本卡。
原MEM02由本對話接續，與其他owner的Gateway／renderer／audio／main無重疊。
共享STATUS／DECISIONS／CONTRACTS留整合owner；本卡先記錄行為契約。

目標：釐清並修正角色、矛盾與不必要澄清的實際模型表現。先以同一既有qwen3:4b-instruct
digest 0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0做固定30題baseline，
再最多一個production候選與同題＋預先凍結未見案例驗證，不反覆抽好分數。
原fixture／rubric／27門檻／正文review gate／模型與採樣設定不改。
只用合成輸入及既有本機模型，不新增依賴／模型、不讀私人DB，不重啟或改服務設定。
初次本機tags超時時WSL剛啟動；後續既有Ollama可讀，未將超時說成模型不存在。

契約：保留全部安全語義、來源原字串與typed packet/native history，
不以case ID／飲品／地名等固定答案分支；模型選擇與工具執行授權保持原界線。
候選僅整理既有policy語言／位置及有條件的affect說明，避免無活動狀態時誤當要求發問。
L1保護來源／角色／取消／預算，L2固定原題與凍結holdout、Codex逐題正文審閱；
若不過就保留結果、撤回不合格production候選，不把測試程式綠當模型品質綠。
每次工作commit，完整記錄失敗／限制，不部署／push／PR。

結果：同模型原題baseline自動22/30／正文21/30；唯一候選自動20/30／正文19/30，
候選C03錯標工具完成、C04/05錯答SIRO偏好，未達原27且安全硬失敗。
保存patch後僅撤回本輪兩個owned production檔，git diff HEAD -- src為空。
12題預先凍結fixture SHA256 11d0d021f92137919d08d3bdcc193fc35dc858667e79c47d874b5209e238abd9，
未看模型新題輸出再調整；候選先在原題失敗，所以新題只跑capture，真模型未跑。
另2次非串流診斷只查provider用量／容量，不列入分數；未發現這兩題輸入截斷依據。
最終215PASS／0FAIL／0SKIP、source穩定receipt；mypy／Ruff／diff check通過。
保留source fences/native history/privacy；無prompt品質改善宣稱。
詳細證據／限制／重現見docs/verification/MEM02-CONTEXT-QUALITY/REPORT.md。
共享文件交整合owner，本輪不是完整記憶產品交付或部署；未push／PR／合併。
