# FIX-020 / D56 — release source identity acceptance

2026-10-14，Asia/Taipei。公開基準 `f3f94c12e690e80ccc945a0bea16b4e91054875e`。

## Current state

FIX-020 為 **REQUIRED_FIX / HIGH / DONE / LOCAL_VERIFIED**，來源是 **ORIGINAL_DESIGN_ERROR / BAD_INTERFACE / TEST_GAP**。RI-005 immutable-source 接入研究先揭露原摘要歧義，因此本卡只修既有發布驗簽邊界。最終乾淨公開 Git checkout 的完整 `scripts/check` **EXIT0 / 637.507s**；**1,813 PASS / 5 原 opt-in SKIP / 7 既有 warnings / 303.43s**。exact-head 雲端 CI 另驗；RI-005 整體仍 PARTIAL。

## Confirmed problem and smallest repair

原 `ReleaseManager._digest` 串接檔名與內容，沒有分隔或長度。自有兩個資料夾 `{a: ALPHAb, b: BRAVO}` 與 `{a: ALPHA, b: bBRAVO}` 的檔案內容不同，但提供相同的 SHA256 輸入 `aALPHAbbBRAVO`。真現有函式的相同摘要為 `3f7ed6f8453e044e0ddab6d7cdd42f00124335380b2fa06b5233c1e7e5c2a447`，見 [collision-proof.json](collision-proof.json)。這是序列化歧義，不是 SHA256 密碼學碰撞。

D39 的完整 HMAC 正確綁定 schema/manifest，但無法修好其所綁定的含糊 source hash。即使後面凍結 source，也可能凍結與批准內容不同、却具有相同摘要的檔案。這是原格式設計錯誤，不要求實作者硬照原格式增加 snapshot abstraction。

唯一 production 修改是 `src/siro/core/releases.py`：新明確 `siro-release-manifest-v2`，使用 domain、8-byte big-endian 檔案數、每個 UTF8 POSIX 路徑長度、路徑、內容長度與精確內容。排序保留既有 Path.parts 語意；完整 canonical JSON HMAC 綁定 v2 tag。舊 `_digest` 和 signing payload 的 v1 語意不變，保留歷史讀取與固定驗簽向量。

v1／None 不可授權 healthcheck、stage、activation、rollback 或 signed launch；在 source hashing 前拒絕。既有 `invalid_manifest`、`invalid_release_target`、`invalid_rollback_target` 結果保持。沒有 silent reinterpretation、自動改 receipt／重新簽署或資料迁移。operator 必須對真實 v2 bytes 明確重新批准為新 immutable release version；原同版本覆寫拒絕保持。

## Evidence and regression baseline

- 原漏洞 RED：[identity-red.log](identity-red.log) **15 FAIL**；修後 [identity-green.log](identity-green.log) **15 PASS**。包括真歧義對、獨立固定 wire/vector、路徑順序、count/name/content/empty/resource/Unicode 改動、算法/tag 錯配、舊版本零效果與 source tamper。
- 正向 fixture 切換獨立記錄：[positive-fixtures-red.log](positive-fixtures-red.log) 的 **42 FAIL / 111 PASS / 48 ERROR** 是 v2 production 配舊 v1 approval 的預期 fixture RED，不能當原漏洞證據；初版 fixture 更新後 **201 PASS**。canonical v1 固定 payload/HMAC 與 legacy schema tamper 保留，unsupported format 改成 v3。
- 初次 clean runner 在測試前中止，因發現 source-selection fixture 改為呼叫 production digest，會降低獨立性。root 恢復獨立 framed-wire oracle，再重啟最終完整檢查；中止 run 是 **INTERRUPTED_NOT_PASS**，不是 PASS。[清理記錄](clean-check-interrupted.json) 證明自有 process group 清空，兩個暫存根移除。
- [preservation.json](preservation.json)：171 個原 source/build/schema 範圍檔案中 170 個 bytes 不變，只有 releases.py 改；134 個原 Python test/helper 檔案中 127 個不變，7 個只有正向 approval 準備與同算法比較更新，新增一份 15-case test。原 assertion 不刪、不弱化，不改 skip、production schema、owner、launcher、Gateway、providers、TTS、UI 或 dependency pins。
- 獨立審查綁 production `c959036b436e817d96db14a971b430c02b2b8c096dee00586e3cdf98de36003e`；22 scoped cases PASS，舊 hash/payload AST 保持，沒有 fallback／自動重新批准。完整原回歸仍由 final clean runner 和 exact-head Actions 各自驗收。

最終 frozen 7 fixtures＋新 15 cases：**216 PASS / 2 既有 warnings / 22.70s**，見 [positive-fixtures-final.log](positive-fixtures-final.log) 與 [fixture-preservation-final.json](fixture-preservation-final.json)。196 個原 assertion 保持；只規範 source-process 中同算法 `_digest`→`_digest_v2` 的選擇，不改預期值／效果門檻。獨立 oracle 完整保留。

真現有 signed launcher/main/Gateway/SQLite/HTTP regression：**3 PASS / 7.36s**；[actual-source-process.json](actual-source-process.json) 詳列三個正常子程序 1→2→1、實際三個 source origins、HTTP ready version/digest、signing key 不進 child、SIGTERM -15／shutdown complete／join、package bytes 不改。每次停止後才寫入下一批合成 conversation/memory/completed ledger；回退到 1 仍保留三批最新資料。另 unsupported ABI／tamper 兩個 child exit1、零 DB 修改、沒有 host fallback。五個 child joined、暫存根清除；clone instrumentation 明示，不代表真私人產品或新 immutable loader。

[rollback-result.json](rollback-result.json)：自有 disposable source copy，精確 reverse 唯一 production 檔至原 `0937b3…`，新 15 cases 重現 **15 FAIL**；reapply 精確 `c95903…` 後 **15 PASS**。其餘 136 個 source 檔保持，工作區不回退，暫存根移除。

[clean-check-result.json](clean-check-result.json) / [完整 log](clean-check.log)：真正 public clone/fetch/detached checkout，覆蓋 final 9 source/test bytes，保留 FETCH_HEAD。Python 3.14.4；Rust **6 PASS**、fmt/build/clippy，Ruff **321**、mypy **254**、schema、原 detect-secrets scanner／strict gate 全部 EXIT0；沒有新增 skip 或放寬 gate。自有 check 子程序 joined、兩個暫存根移除、工作 source hash 全保持。scanner 不掃主工作區私人 runtime 資料。四份 evidence reproduction scripts 額外 format/lint PASS；rollback helper 僅 list concat→starred style 修正，不改其執行參數／production，也不冒稱原 raw logs 是此後 bytes 的重新執行。

## Architecture, roadmap and freeze zones

Overall health **YELLOW**。本卡恢復既有「批准確切檔案內容」不變量，沒有新 owner、scheduler、SDK loader、updater 或循環依賴。原 source signing 設計有缺陷；原 skills digest 已有 path/content length framing，沒有此相同缺陷，**FALSE_POSITIVE**，保持不動。

RI-005 保持 **PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**；FIX-020 完整 local 驗收解除其 source-format blocker，exact-head cloud 另記。D52 source selection/version/readiness 行為已用 v2 fixtures 重新驗證；原 RT-011/013/015 scoped DONE、D39 schema signing、D48–D55 其他限定結果保持，不重編或排名。

KEEP/SPLIT 下一三個已有範圍：RI-005 captured exact source/import window；RI-005 approved maintenance-to-runtime handoff 與 old-writer adoption；RI-006 safe 定位證據到最小真修復提案。這些是待實作驗收的既有工作，不因原方案寫好就硬接未證的 OS 路徑。

Freeze：已驗 v2 identity cases／合成測試/evidence **GREEN**；release 元件／Core/Gateway/UI 仍 **YELLOW**；live data／migration／permissions／formal release **RED**。Hermes 概念只保留具體 caller 的能力；**REJECT** 第二套 updater／owner／自批自改，以及未使用的 snapshot abstraction。

## Remaining gates and research

[RI-005 prototype review](../RI-005-capture-2026-10-14/prototype-review.md) 與真 kernel probe 證明 tiny sealed-source projection、late import/resource、EROFS、FD 清理等 primitive 可行。它也證明 direct bwrap exec 的 monitor TERM 不會 graceful drain，且 mutable destination alias 不能由 snapshot FD 自動修好。因此本卡沒有把 prototype 接入 production；不能以九項 kernel primitive PASS 放行完整 Gateway、host capability 或手動發布。

下卡需在既有 launcher composition 驗證 private source root、明確 dependency 假設、可信 child identity／TERM forwarding／join、capture limits，再驗 maintenance handoff。原 source/import race、mutable dependencies、CLOEXEC handoff、old/unmanaged writer absence、正式 adoption、跨平台、power loss 仍有 gate。舊未受管 writer 的不存在不能靠 PID、新 lease 或成功 BEGIN 偽證。

目前 v2 的讀取邊界仍沿既有 file-tree 範圍：未新增 bounded capture，不綁 empty directories、permissions、host dependencies，也不承諾阻止同 UID 注入。這些限制明示，不能把名稱叫 v2 當作完整 runtime package 保證。

## Rollback and publication boundary

回退先撤 release 執行入口，再只 reverse 本卡 source/fixture scope；不恢复舊 DB、不刪 receipt/history、不重新允許 v1 execution。disposable reverse/reapply 證明可還原 source，不是正式安全發布許可。

所有碰撞／DB／HTTP／process／kernel fixture 都是自有合成資料。沒有操作 live8026、私人 DB／chat／WAV／key／config／models、GPU 或 formal deployment。Git push 只發布程式與審閱證據，runtime 更新另有門檻。Codebase Memory 無可呼叫工具，graph/reindex **NOT_RUN**；以 source、rg、測試与精確 hash 為證。
