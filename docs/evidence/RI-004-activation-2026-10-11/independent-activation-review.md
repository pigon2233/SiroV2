# RI-004 D47 independent activation review

日期：2026-10-11（Asia/Taipei）。**Status: VERIFIED_SOURCE_REVIEW — no remaining confirmed scoped blocker**。本文件保留先前的 boundary／最小驗收，再記錄實際局部反例與修復後的驗證。此獨立審查者没有production／全域文件修改；經主 agent 明確授權新增唯一測試檔 `tests/integration/test_skill_activation_review.py`。只使用 temporary synthetic SQLite／固定候選／controlled fixtures；沒有live8026／私人資料／真模型／部署。

## Existing boundary evidence

- `services/tools/skill_candidates.py` 的 `_prepare` 先掃原ToolCatalog全部aliases（含unavailable／hidden），成功report仍installed=false／enabled=false／authorizes_execution=false，四個檔案是固定trusted模板，disposableverification projection已清理。D47不得從client檔案/PASS取得新authority，不能預先放dormant alias讓初次prepare永遠existing_unavailable。
- `services/presentation/gateway.py` 的candidatePOST先require_origin＋require_token，strict `SkillCandidateInput`只有capability；runtime/control snapshot為read-onlymetadata；tools-off取消candidate，shutdown finally維持剩餘cleanup。新的install／enable／revoke沿同入口，不造directexecuteHTTP。
- `persistence/skills.py` 既有`install`是UPSERT，不能用來符合新同版不覆寫需求；舊方法保留compat，新insert-if-absent局部入口須有反例。`set_enabled`原已對讀取row hash/root作CAS，但尚無expected displayed identity参数；D47 expected identity須防stalecontrol選中另一package。
- `SkillDispatcher`的enabledcheck位於supervisor semaphore之前。前輪合成queued revoke已證實disable row後queued job仍可進入worker；見 [`FIX-011 future activation findings`](../FIX-011-2026-10-11/repair-definition.md#future-activation-findings--separate-defer-gates)。D47必須由同一productowner先fence availability/admission，再cancel/join全部active及queuedjobs；單用registry disable不滿足需求。
- `ToolCatalog.require/capture`是原freshavailability／schema邊界，`ToolOrchestrator`原authorized contextual executor有run cancel／deadline fence；`IntegratedCompanion._model_capabilities`在candidateprofile取同一catalogsnapshot。D47不需要第二個capabilityregistry或chat入口。

## Minimal malicious / authority acceptance

| Controlled case | Required observable outcome |
| --- | --- |
| install body帶files／schema／path／PASS／code／profile／enable或非strictreview_id/hash | HTTP422，寫檔／registry／catalog effects全部為零；既有token/origin拒絕亦在effects之前 |
| unknown／expired／被下一份review取代的review_id，或錯packagehash | 固定拒絕，沒有安裝／啟用；monotonicTTL／owner epoch而非clienttimestamp |
| client修改已export／returnedreport的files或verification | install仍只使用server-held immutablecapturedtemplate；不能將client資料換進批准 |
| wrongsource/tests/proposal digest、verificationproposalUUID/path/status/cleanup binding | `remember`拒絕，不發出可安裝review_id；只用exacttrustedtemplate，不hostimport |
| repeatedinstall與同id/version已存在不同bytes／root／state | 新方法False；既有row三欄hash/root/state不變，enabled同版不能被覆寫。衝突managedfiles不得先overwrite再發現DBconflict |
| enable時receipt／packagebytes／mode／root／schema被改、alias／extra／unknownrow | failclosed，availability不能變true；disabled/revokedrow即使檔案毀損仍可revoke，不能靠壞檔阻止disable |
| 已enable但直接argument-onlyexecutor呼叫，或contextauthorized=False／cancelled／deadlineexpired | 無worker dispatch。唯一實際execution是原ToolProposal批准後的authorizedcontext→owner→既有Dispatcher→D46strictworker |
| invalidtext／超UTF8bytes／lines，或stubworker錯nestedtype／count／itembounds | 固定拒絕，不把dict存在當作可信checklistoutput；counts必須exactint，bool不能冒充int |

## Revoke / cancellation / restart acceptance

1. **實際queue反例**：temporarySQLite／managedpackage先install-disabled、另一步enable；hold第一個execution，第二個已在owneradmission/semaphorequeue；revoke在釋放第一個之前開始。先availability=false，active及queuedtask都join；queued不得到worker，activePID不存活，fresh/staleToolCatalogrequire都無法產生success。使用stubworker只能證明ownerqueue，實際OSPID驗收另列。
2. **durablewrite取消**：controlledto_threadpackage/receiptwrite與SQLitecommit在publish前阻塞；single＋repeatedcancel、tools-off或close後，owner仍busy/owned直到join。不得取消後背景lateenable，不刪掉已commitrow所指package；不確定結果要readback/reconcile，cleanupfailure保持typedfailure。不把CancelledError當作transaction已rollback。
3. **concurrentcontrols**：enable與revoke／tools-off／close競賽，ownerfence先於await。遲到enablecommit不能復活可用狀態；tokens/contextcancel亦要末端check。新install/enable在closed/suspended時拒絕，revoke可在tools-off操作。
4. **restart正負控制**：新owner＋同一temporarySQLite/managedroot/catalog。只有exactfixedtemplate＋outside-packageapprovalreceipt＋matchingregistryidentity可重建descriptor；enabled保留、disabled/revoked保留unavailable。改bytes、刪receipt、receiptforgery／symlink／wronghash／oldlegacy/unknownrow皆不可自動repair／swap／enable。Server-heldreview不跨restart復活。
5. **snapshot／UI／HTTP未知**：GET/runtime與controlreconnect不呼叫remember/install/enable/revoke；HTTPnon401或unknownoutcome不自動重送。Client只讀status做reconciliation；token401僅在serverpre-effect拒絕時重取token。Source／error用textContent，不能注入HTML；approve-install與enable分開，revoke後立即明示不可用。

## Confirmed local findings

以下均為 D47 新 activation owner 的局部 `REQUIRED_FIX`／`IMPLEMENTATION_BUG`；不是 D46 strict worker 或 registry foundation 的未確認缺陷。修復由主 agent 執行，此審查者沒有修改 production source。

| Actual failure | Confirmed root cause | Minimal repair / observable invariant |
| --- | --- | --- |
| Revoke 遇到 typed worker cleanup failure 後，記憶中的 availability=false，但 actual SQLite row 仍 enabled；fresh owner 會恢復 enabled | `_disable` 先 await `_drain`，其 exception 使 durable disable 未執行 | Drain 全部 owned jobs，仍嘗試 identity-bound durable disable，最後保留原 `ExecutionCleanupError` |
| Repeated cancellation during actual off-loop restore publication，外層回報 cancellation，但 late initialize 仍 publish enabled descriptor | Public cancel 增加 epoch；initialize 最後 availability publication 未檢查原 epoch | Public initialize 捕捉 epoch，末端 enabled publication 同時檢查 epoch／closed；取消讀取保留此前 explicit durable approval |
| Successful dispatcher result 的 watcher cleanup 階段，caller cancel／token cancel／deadline／revoke 後仍回報 success | `return job.result()` 已在 finally 前求值；join watcher 可吞 late cancellation，沒有末端 fence | Cleanup 後再檢查 caller cancelling count、context、epoch／availability，才發出 result；primary typed cleanup failure 不被晚到 cancel 遮蔽 |
| Active remember 在 complete-template hash publication 被 suspend 中斷後，仍保存 review | remember 未受 control owner 追蹤，epoch 在 hash await 後才採用新值 | remember 納入同一 control owner，在 hash await 前捕捉 epoch，末端檢查 |
| Unsupported strict runtime 的 enable 洩出原 `SkillExecutionError`，沒有 fixed activation failure | 新 pre-enable developer verification 的 failure 未轉成 activation public error | 包装為 `SkillActivationError`；actual SQLite row 和 descriptor 均維持 disabled，沒有 host fallback |
| Remember 已排在 blocked initialize 之後，suspend 先同步 fence，舊 queued remember 開始時卻採用新 epoch，仍保存 review_id | epoch 在 serialized `_remember` 內才捕捉，並非 public remember admission 時 | Public remember 捕捉／傳遞原 epoch，queued operation 開始及 publication 都拒絕 stale epoch；第十九項 regression 已通過 |

## Captured evidence and test scope

- [`independent-control-probes-before.json`](independent-control-probes-before.json)：actual temporary SQLite／receipt／fixed package；dispatcher cleanup failure 為 injected typed failure，restore publication 以 controlled off-loop seam 阻塞。並非實際 kernel cleanup failure。
- [`independent-late-cleanup-before.json`](independent-late-cleanup-before.json)：successful dispatcher stub＋controlled cancellation watcher 的 caller/token/revoke late-cancel 反例；只證明 owner publication/lifecycle invariant。
- [`independent-review-before.log`](independent-review-before.log)：初始 owned 18 cases，**8 failed / 10 passed / 3.95 s**；wrong-valid-format hash 與八項 actual restart tamper controls 已通過，並未假稱它們曾失敗。
- [`independent-review-after.log`](independent-review-after.log)：上述 source 局部修復後 **18 passed / 4.24 s**，尚非最終 source freeze。
- [`independent-queued-review-before.json`](independent-queued-review-before.json)：actual fixed candidate report／temporary SQLite，舊 remember queued before suspend，review publication=true，review retained=true，enabled=false。此反例沒有越過 explicit execution approval。
- [`independent-queued-review-before.log`](independent-queued-review-before.log)：新增第十九項 regression **1 failed / 18 deselected / 0.30 s**；修復前未拋出預期 `SkillActivationError`。
- [`independent-review-final.log`](independent-review-final.log)：root FINALFREEZE 後 owned nineteen cases **19 passed / 4.67 s**；owned test 的 Ruff check／format／mypy 皆通過。先前 RED logs 不覆寫。
- `test_skill_activation_review.py` 的 hash 拒絕檢查 actual SQLite rowcount=0；restore tamper 包含 source bytes／symlink／exec mode、missing receipt／bool-int forged receipt／receipt symlink、registry hash／path；unsupported platform 使用 actual strict worker public API，沒有 mock success。
- [`lifecycle-report.md`](lifecycle-report.md) 由另一測試 owner 記錄 actual OS worker active＋queued revoke、SQLite after-UPDATE-before-COMMIT cancellation 等 **7 passed**。請以其 controlled stage、PID／request-workspace observations 及 injected-error 限定為準；不可把本文件的 stub assertions 擴寫成 OS 證明。

## Current source assessment and retained gates

目前 verified path 為固定 server-held review → explicit install-disabled → separate explicit enable → 原 ToolCatalog／authorized ToolProposal context → 同一 activation owner admission → 原 SkillDispatcher → D46 strict worker。Revoke／tools-off 先 availability/epoch fence，再 join owned work並持久停用。沒有第二個 registry／DB／planner／chat execution endpoint，也沒有 default trusted-local 或 RI003 worker 重構。

最終 [`independent-source-binding.json`](independent-source-binding.json) 捕捉四個既有改動＋七個新 production/test 檔案，與 root `preservation.json` 的十一項 final hashes 完全一致；258 baseline 檔案中其餘 254 檔未改，D46 的七項 source/test hashes 全部未改。Owned test hash `114606368a57341665ce5cf4aeb9fa078fd0dd59c7bb8b753cdad0edb1242197`；activation owner hash `53672d9b8a6555a1644fd732d41380f95677298df557552587e8489dc07d2dad`。[`independent_source_binding.py`](independent_source_binding.py) 可重播 source-only 檢查，沒有 source mutation。

上方 acceptance 表是原先 required matrix，並非此審查者逐項實測宣告。Gateway／UI／composition／整體 regression／全域格式與型別／exact-scope rollback 由主 agent 與 product owner 的 artifacts 提供；此十九項結果不替代它們。此審查沒有剩餘已確認的 D47 scoped blocker，沒有因 speculative future risk 擴張本卡。

## Final UI history-label supplement

主 agent 的後續真瀏覽器畫面顯示：下方 activation 已確認 installed，上方準備紀錄仍寫「尚未安裝」。此項是局部 presentation `MINOR_FIX`／`IMPLEMENTATION_BUG`，沒有新增 authority 或改動 activation owner。此審查只讀核對 late diff：`index.html` 新增 `labelSkillCandidateHistory(state)` 與兩個呼叫點（accepted runtime metadata／successful explicit activation）；`test_frontend_skill_activation.py` 只追加兩項 regression，其餘九個 D47 source/test hashes 完全不變。

Helper 只在 `installed === true` 且 server state hash 等於 displayed review hash 時，用固定 `textContent` 將紀錄標成「準備時的審查紀錄；目前已安裝」。沒有改動 `skillCandidateReview`、source/files、verification、export、trust_level、installed/enabled 或 authorizes_execution 原始欄位，也沒有新增或重送 HTTP 操作。兩項 tests 分別核對 install/enable/revoke 後 historical label＋actual Blob export 保留原 unreviewed/installed-false/enabled-false，及 metadata wrong-hash 不 relabel／matching-hash 才 relabel／refresh 不送 activation。

- [`review-history-before.log`](review-history-before.log)：product owner 保存 **2 failed / 25 deselected / 0.29 s**。
- [`review-history-after.log`](review-history-after.log)：actual page script＋synthetic DOM/socket，**78 passed / 3.84 s**，含二十七項新 frontend 及五十一項既有 candidate/control cases。
- [`product-new-final.log`](product-new-final.log)：更新後 **92 passed / 3.38 s**（65 HTTP＋27 frontend）；這些是 controlled product fixtures，沒有真模型宣告。
- [`card-after-history.log`](card-after-history.log)：root whole-card **189 passed / 17.12 s**；[`full-after-history.log`](full-after-history.log)：root full regression **1391 passed / 5 deselected / 3 warnings / 154.61 s**。此審查讀取已保存輸出，沒有另行重跑全套或聲稱操作 live service。

`independent-source-binding-phase1.json` 保留第一次 freeze 的歷史 hashes。最終 `independent-source-binding.json` 已在 FINALFREEZE2 master preservation 後重生並一致：只 `index.html`／new frontend test 分別改成 `9dee99a3bc565dde30b1d2c26164e1fe4861f3b0e626aa26316b42f80e007472`／`ac7c449b564e24179dc4b474a100cd312f405a9d820c4a3c4e2af1976566b6da`，其餘九檔不變、254 baseline 檔及 D46 七檔仍未改。Late two-file review 沒有剩餘已確認的 scoped blocker。

保留未擴張門檻：僅此固定 pasted-text template；既有 trusted-local metadata equality debt、同 UID 敵意、OS runtime assumptions、aggregate kernel RAM、安全審查／任意 generated skills、release 和真模型產品體驗均未被此卡認證。固定模板產品接入通過不代表任意模型生成 source 可自動 install／enable；不因新增 abstraction 而重構已解決的 D46 worker。
