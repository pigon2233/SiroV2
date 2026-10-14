# FIX-020 frozen publication scope / privacy review

2026-10-14（Asia/Taipei）。**NO_CONFIRMED_SCOPED_PUBLICATION_BLOCKER；unresolved 0 / true secrets 0。** 本 reviewer 只做指定公開範圍唯讀驗收，僅新增此兩份 audit evidence；沒有修改 production/tests、commit 或操作 live/private runtime。

Captured cutoff：`2026-10-14T09:42:54.348883+00:00`。57 個明列 inputs（1,206,611 bytes）全部在寫入本報告前重新核對與 frozen SHA256 一致；完整路徑、bytes、SHA256、逐項 findings 與實際命令收錄於 [scope-review.json](scope-review.json)。cutoff 後修改不在此次驗收內。

| Scope | Explicit files | Detector findings | Unresolved |
|---|---:|---:|---:|
| source / tests | 9 | 0 | 0 |
| tracked public docs | 11 | 0 | 0 |
| specified public synthetic evidence | 37 | 194 | 0 |

實際 detect-secrets 1.5.0 使用 owned neutral snapshot 與 explicit file arguments，27 plugins／既有 thresholds 保持；沒有 `--all-files`、新增 allowlist 或放寬原 CI strict gate。`--no-verify` 僅禁止把候選值送到網路驗證。三組掃描皆 EXIT0；偵測 JSON 並逐項審查，EXIT0 本身不當作無候選的證明。

194 個候選全部是 Hex High Entropy String，152 個唯一公開值；每筆以 detector hashed_secret 對回 exact file/line 的實際字串，再依下表確認來源。沒有使用整批 hex 自動豁免。

| Confirmed provenance | Findings |
|---|---:|
| 目前允許 scope 檔案的精確 SHA256 | 37 |
| 明示 INTERRUPTED 的舊 scoped fixture fingerprint | 1 |
| 8 份 scoped 公開 parent 檔案的重算 SHA256 | 10 |
| 公開 baseline.tests fingerprint metadata | 127 |
| 已核對的公開 parent Git object ID | 8 |
| 原 launcher／Gateway 公開 source fingerprint metadata | 4 |
| 固定 tiny kernel fixture bytes 重算 digest | 1 |
| 固定公開 counterexample bytes 重算 digest | 2 |
| 自有 instrumentation release package fingerprint | 4 |

公開 parent `f3f94c12e690e80ccc945a0bea16b4e91054875e` 與 8 個 scoped 歷史 source/test 指紋獨立核對。baseline 的其他 test fingerprints 只審查明確 `tests/<public-path>` JSON metadata，沒有讀取或冒稱重算那些 scope 外檔案。兩個合成 legacy/kernel 摘要以記憶體固定 bytes 重算。actual-source package 摘要依 final fixture producer／三個版本與 before/after/ready 欄位核對；已清除的 package 不在本 audit 重建。

隱私來源核對：logs 的 `.siro-data/tokenizers` 是自有 `/tmp` clean clone 的公開 pinned 資產；`GROQ_API_KEY` 是原 opt-in skip 訊息／env 名稱，未含值。repo/home/pypinyin 路徑與 raw logs 保留，不讀所指的私人資料。實際 5 child、清理、rollback 與完整檢查證據均已納入 37 份 exact input；它們的執行結論屬原 producer，不冒稱此 audit 重跑。rollback helper 後續兩行 style 修正與原 raw run 的關係照 REPORT 保留。

排除：其他舊 untracked／private DB、chat、audio、key、config、models、main `.siro-data`、live8026／GPU，以及本 scope-review.json/md 自身、root 的 publish-inputs.json 自參照 metadata 和之後 publication／commit／remote-CI receipt。audit output 無 self-reference hash；此結論不能覆蓋 cutoff 後 bytes。自有 neutral snapshot 與所有 scan 子程序已清理／join。

本次只解除 frozen 公開發布範圍的秘密／隱私疑慮，不放行 formal deployment，也不解除 RI-005 immutable import、dependency identity、unmanaged writer、maintenance handoff、lifecycle 或 FIX-002/005/006 產品驗收門檻。
