# 鍵盤略過導覽的 source-only 回退

在 SiroV2 根目錄：

```sh
.venv/bin/python docs/evidence/T10-KEYBOARD-2026-10-18/rollback/verify.py
git apply --check docs/evidence/T10-KEYBOARD-2026-10-18/rollback/rollback.patch
```

以上不改目前checkout。verifier僅在自有temporary directory真正撤回／重套，逐byte驗證before/after及合成latest-data sentinel，再清理。BASELINE_COMMIT與SHA256SUMS綁定本卡dirty baseline；before已含search／DETAIL／SETTINGS，非HEAD原始檔。

rollback.patch方向為目前KEYBOARD→before；reapply.patch為相反方向。後續source若改變，verifier會拒絕drift；先依新增順序撤其後切片，或審查並重建patch，不能硬套。這不是正式部署回退或DB還原；不使用git checkout HEAD丟掉其他未提交工作。
