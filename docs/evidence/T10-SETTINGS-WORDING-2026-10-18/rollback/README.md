# 設定用語切片的 source-only 回退

在 SiroV2 根目錄執行：

```sh
.venv/bin/python docs/evidence/T10-SETTINGS-WORDING-2026-10-18/rollback/verify.py
git apply --check docs/evidence/T10-SETTINGS-WORDING-2026-10-18/rollback/rollback.patch
```

兩個指令都不改目前checkout。verify.py只在自己建立的temporary directory真正套rollback/reapply，驗證精確before/after與合成latest-data sentinel，再清理。

BASELINE_COMMIT記錄原Git版本；index.before.snapshot是本輪開始時已含D69搜尋與D70詳情的dirty HTML，after是本切片結果，SHA256SUMS綁定兩者。這是單一HTML的完整回退基線，不是全repo或資料庫備份。未來source不同即拒絕，不強套patch。

若要再撤回DETAIL，先撤本SETTINGS切片，再使用DETAIL自己的rollback package；本輪已在隔離目錄驗證此順序與反向重套。既有DETAIL回退對新source報drift是預期的保護，不修改歷史快照。

正式部署回退未在本輪執行。不要用git checkout HEAD撤掉其他未提交功能，也不要還原舊資料庫。
