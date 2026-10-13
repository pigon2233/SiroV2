# D52 exact source rollback rehearsal — preliminary

2026-10-13（Asia/Taipei）。Independent subagent；只新增rollback evidence，production/tests/data/index沒有修改。此結果為當時snapshot；true process test仍待rootfreeze，**不能當final acceptance**。

273個baseline public source/test/build files中，只有D52明列existing3檔不同；其餘270 bytes保持。四份新tests不在baseline。Source-only patch精確7檔：Core releases、companion launcher、Gateway＋selection/ready/signed-launcher/source-process四tests。

在disposable temporarycopy執行 `git apply --reverse --check`、reverse、forwardcheck、reapply全部exit0。Reverse後273檔hash吻合baseline、只移除4新tests；reapply後277 current檔bytes完全吻合。最後temp root移除，working source起訖相同。

D51四source（SQLite backup、CLI backup wrapper、兩backup tests）、D50 data-owner與operations fences逐檔保持；沒有撤銷其修復。Source patch不含DB/schema/data/config/activepointer/release/history檔，也不依次呼叫rollback/restore/deploy。精確source回退是工程復原能力，不授權切實際服務或呼叫舊版危險資料restore。

命令：`.venv/bin/python docs/evidence/RI-005-launcher-2026-10-13/rollback-rehearse.py --label preliminary` → PASS；script Ruff lint/format →PASS。結果與7檔afterhashes：`rollback-preliminary.json`；exactpatch：`rollback-repair-preliminary.patch`。

等待root final7hash freeze後，以 `--label final --freeze <root-freeze-json>`重新驗證、另存final結果/patch。若任一finalsource与freeze不同，script拒絕；不在workspace試apply、不操作workingGitindex。此probe不讀private／untrackedmodels或現用settings。
