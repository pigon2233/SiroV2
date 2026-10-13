# FIX-008 — Protected source/destination path verification

日期2026-10-10；**DONE / VERIFIED，限D38明示dialect與path guard**；最後完整回歸829PASS／5 real_provider未選／3既有warnings（112.86s）。範圍僅既有PatchVerifier path preflight；没有將候選套到實際SIRO、启用不可信checks或自動發布。

## 問題與結果

原parser只讀+++ b/，漏掉/dev/null刪除的來源；protected delete搭配一般修改可以驗pass。timestamp／非canonical alias也可讓raw-string protected比對失效。修補同一private方法：先驗完整有限text dialect、計數消耗hunk body、取得舊／新first-seen聯集，再按原protection清單拒絕。新增／修改／刪除與一致rename+hunk保留原驗證；unsupported／矛盾格式整份rejected_invalid_diff。沒有新增parser依賴、registry、service、sandbox或修改公開report／checks。

只改[core/evolution.py](../../../src/siro/core/evolution.py)，新增[test_patch_path_protection.py](../../../tests/integration/test_patch_path_protection.py)。契約在source前寫入[D38](../../DECISIONS.md)與[CONTRACTS](../../CONTRACTS.md)。路徑須canonical relative POSIX，拒絕dot／dot-dot／empty component／.git／whitespace／control／quoted／backslash；LF與final separator明示。支持常見plain unified text與一致Git metadata；binary/copy/mode-only/rename-only/timestamp/ambiguous等不支持。這是保守格式限縮，不是通用Git parser或重設evolution架構。

## 實際證據

- 首批51正式負向fixtures在production改前：[37FAIL／14PASS](path-protection-before.log)，0.49s。
- 最後62 tests對精確pre-card source的temp副本：[46FAIL／16PASS](path-protection-complete-before.log)，0.49s；記錄source SHA／import path／temp cleanup，沒有把新增API缺失冒充root-cause紅燈。
- [修後新舊專項](path-protection-after.log)：63PASS，0.36s。protected source/destination與invaliddiff均spy證明零_tree_digest／mkdtemp／_run，因此在copy/apply/check之前拒絕。合法modify/add/delete/rename、checks pass/fail、unappliable、真正Git apply的header-looking hunk文字均驗；fixture source bytes不變、temp workspace已刪。
- [獨立Git metadata probe](git-metadata.json)與[重現程式](git_metadata_probe.py)：只跑git apply --numstat -z、零apply/check／零文件；rename只報新path，timestamp還原真正path，hunk內標頭為文字、Git可接受矛盾diff --git header，不能用metadata輸出直接當完整policy授權。
- [三個synthetic CLI相鄰case](operational-cli-after.log)PASS／一個無關runtime start-stop未選；不是正式環境backup／部署驗收。
- [原始驗證](path-protection-verification.json)包含source/test/log SHA、source保存及已驗／未驗範圍。独立read-only reviewer另檢查hunk counters／crossed metadata與path alias，結果記於independent-review.json。

## 保存與回退

[baseline](baseline.json)為FIX-002完成後的dirty source，不是HEAD；225基準檔案僅evolution.py改動，之前browser、RI-002、voice/session工作均保持，[保存](preservation.json)與scoped secret scan0 findings。

[精確兩檔patch](repair.patch)、[回退](rollback.json)：temp副本reverse check／舊SHA／移除新test／reapply SHA全PASS。沒有DB／release／active pointer或運行中服務回退。回退舊parser後自動checks/promotion必須保持停用，不能把已知漏洞版本當安全fallback。

局部protected-path漏洞解除後，**untrusted checks仍受真正OS隔離與可信check allowlist gate**；same-user copy不是sandbox。本卡不接runtime caller，不宣稱自主改碼、生成技能或發布已完成。既有protected清單不擴大，原T/RT歷史保留，FIX-007／009保持獨立。

最後[checks](checks.json)：format221／lint／mypy211／schemas／git diff --check PASS。離線全套與[獨立review](independent-review.json)均過，無新增證實的path blocker；untrusted OS隔離及其他FIX gate保留。
