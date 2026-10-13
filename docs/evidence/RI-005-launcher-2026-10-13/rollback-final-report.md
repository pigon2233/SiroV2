# D52 exact seven-file source rollback — final

2026-10-13（Asia/Taipei）。Independent subagent；production/tests/data/index唯讀。**Final PASS**，綁定root `source-freeze.json` seven source hashes；freeze SHA256 `3a288291a6628cf9b971d4aeb2d901926f8c39143a1084ccc14def1eb3f7e38e`。

## Exact scope

Baseline273 public source/test/build files：只有existing3 changed（`src/siro/core/releases.py`、`scripts/launch_companion.py`、`src/siro/services/presentation/gateway.py`），其餘270oldfiles bytes完全保持。New4是 `test_release_launch_selection.py`、`test_release_ready_identity.py`、`test_signed_companion_launcher.py`、`test_release_source_process.py`，都不在baseline。

精確source-onlypatch：`rollback-repair-final.patch`，SHA256 `32ee18020da76e986777c5f9a8060a330e85ddbf94f087ed3bfae0a0ad980096`；before3與capturedbaseline逐檔匹配、after7與finalfreeze逐檔匹配。Hash明細完整在 `rollback-final.json`。

## Actual disposable rehearsal

1. 在temp根只複製273公開baselinepaths的currentbytes＋4newtests，不複製 `.git`、任何private資料或現用settings。
2. `git apply --reverse --check` →exit0；reverseapply→exit0。
3. Reverse後273files逐檔hash吻合原baseline，4newtests不存在。
4. Forwardcheck→exit0；reapply→exit0；277currentfiles逐檔bytes完全吻合原snapshot。
5. Temp root移除；working273＋new4起訖bytes一致，sourcefreeze7仍匹配。

D51 SQLite／CLI／兩backuptests、D50 data-owner與operations exacthash保持。SQLiteStore的D49restorebody由D51原source保留，本卡未觸整份SQLite；没有撤銷D49／D50／D51修復。

命令：

```text
.venv/bin/python docs/evidence/RI-005-launcher-2026-10-13/rollback-rehearse.py --label final --freeze docs/evidence/RI-005-launcher-2026-10-13/source-freeze.json
```

exit0／`passed:true, freeze_bound:true`。Evidence script Ruff lint/formatPASS。

首次final指令的freeze parser只支援`hashes`，rootfreeze欄位為`source_sha256`，在任何disposableapply前KeyError停止。只修evidence parser支援root格式＋要求exact7keys＋记录freezehash；再完整rerun以上finalPASS。這是evidence-reader defect，不是productionfailure，也沒有修改production/tests或放鬆hash門檻。

## Operational limits

此patch只復原D52 source與新tests，不含DB/schema/data/config/activepointer/receipt/history。工具從未在workspaceapply、操作Gitindex、呼叫ReleaseManager.rollback/restore/deploy。不得把工程source回退PASS當正式服務切版批准；實際運行版本還需人工maintenance／first-adoption舊writer停止／leasehandoff與readiness gates。不得因source回退而restore舊資料備份，latest conversation/memory/completedledger保留原位。

後續source不同於finalfreeze就拒絕沿用此final結果；需要新snapshot與exactrehearsal。此報告不替代rootfullsuite或actualtwo-versionHTTP證據。
