# T30 驗收證據

日期：2026-09-26｜結果：PASS（L1 + SQLite integration）

`ProceduralCandidateGenerator` 只接受至少兩條、結構一致、trusted 且每一步成功的 trace。候選會保存
source trace UUID、workflow hash、既有 capability 集與最小 fixture；`token`、`secret`、`password`、
`api_key` 等鍵及 Bearer/Groq 類字串都在保存前改為 `[REDACTED]`。

不可信 trace、含失敗步驟或只有一次成功都只得到明確 rejected reason。候選的唯一狀態是
`candidate`，`SQLiteProceduralCandidateRepository` 沒有 enable/install API，因此無法從 trace 自動變成
active skill 或增加 permission。

`008_procedural_candidates.sql` 保存 review data；`tests/integration/test_procedural_candidates.py` 驗證
redaction、拒絕規則與重啟後保存。完整 `scripts/check`：Python 123 passed、5 個明確 external opt-in
skipped；Rust 6 passed。
