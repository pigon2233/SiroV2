# FIX-026 — 歷史驗證快照的 secret scan 誤報修復

日期：2026-10-16（Asia/Taipei）。**DONE / CLOUD_VERIFIED**：修復已推送，exact-head Actions成功。。

940bdb7 新追蹤舊驗證資料，Actions [38866208100](https://github.com/pigon2233/SiroV2/actions/runs/38866208100)
完成2129 Python PASS／5原opt-in SKIP／7warnings（226.32s）、24 Rust tests與靜態／schema checks，
最後 secret gate 因1332個已審核誤報失敗。獨立乾淨Git副本重現相同1338個detector findings，
原六個public tokenizer pins照舊允許，剩1332個位於13份歷史檔案。

## Exact-head cloud結果

修復commit `5e4506a`：[Actions 38868369775](https://github.com/pigon2233/SiroV2/actions/runs/38868369775) **completed / success**，
完整scripts/check step成功：**2166 Python PASS／5原opt-in SKIP／7warnings／261.93s**，
24 Rust tests、fmt/build/clippy、Ruff338、mypy268、schema與原scanner／strict gate全PASS。
遠端main已確認同一完整SHA，沒有以local PASS或舊commit代替。本卡交付阻擋解除；
正式發布／實板／其他產品品質gates保持。[機器可讀證據](CLOUD_ACCEPTANCE.json)。

## 實際修正

只改 `scripts/check_secrets.py`：沿既有fail-closed helper加入13個固定相對路徑，完整檔案SHA256、
finding數量與完整tuple batch SHA256三者全吻合才承認已審核誤報。tuple固定為filename／line／type／
hashed_secret／is_verified，排序list保留duplicate；不以一般hex／JSON欄位名判定可信。

原scanner、exclude正則、六個tokenizer pins、13份歷史檔案bytes與位置、原25個tests均不改。
沒有搬快照、改production、依賴、CI環境或其他未提交修改。目錄／檔案symlink與OSError均不承認。
snapshot或scanner結果日後變更需重新審核，不會自動擴允許範圍。

12份metadata合計1331個finding，包括Git／source摘要與GPU log的輸入／輸出內容指紋；另1份舊測試
只有字面量synthetic credential。GPU log只審核其metadata，沒有讀取或重新hash私人音訊。
逐檔語意見 [semantic-audit.json](semantic-audit.json)，完整雙綁定與count見 [matchmap.json](matchmap.json)。

## 驗收與反例

| 檢查 | 實際結果 |
|---|---|
| 新測試對原helper | 2 FAIL／34 PASS／6.16s；誤報與finding排序兩個正例仍拒絕 |
| 原25＋新37測試 | **62 PASS／12.60s**；[實際log](gate-tests.log) |
| 原掃描設定的乾淨候選 | **1338 findings／14 files，gate EXIT0／6.869s**；[CLEAN_SCAN](CLEAN_SCAN.json) |
| 最終index範圍重驗 | 本卡code／文件／證據疊HEAD，**1338 findings、gate EXIT0／16.496s**；[INDEX_SCAN](INDEX_SCAN.json) |
| 全專案Ruff | format338 files、lint PASS |
| helper與新tests type | mypy2 files PASS；完整候選mypy268 files PASS |
| 獨立review | 13個pins均與原report重算一致；混合原6pins可通過；12個batch做同數量duplicate替換全部拒絕 |

自動測試包括：逐一改13份snapshot bytes；變line／type／fingerprint／filename／verified flag；
少項、多項、duplicate及同數量duplicate替換；其他path／alias；missing／directory／leaf與parent symlink；
讀檔PermissionError；真scanner在snapshot JSON／舊測試／新source／workflow加入合成credential後仍拒絕，
且錯誤輸出不含該值。原tests未改，沒有新增skip或降低門檻。

第一乾淨候選曾多出一項本輪test程式中的字面量synthetic誤報，保留 [FIRST_CLEAN_SCAN](FIRST_CLEAN_SCAN.json)。
只將測試替換字串從參數與JSON字面值組合，沒有再加例外；真scanner注入credential測試仍PASS。
新加的一個同數量duplicate案例是在最初36-case RED之後補上，故最終是37新case。

重現：

```bash
uv run pytest -q tests/integration/test_ci_secret_gate.py tests/integration/test_ci_snapshot_secret_gate.py
scripts/check
```

完整本機scripts/check未在含私人caches的dirty工作區重跑；乾淨候選掃描與靜態檢查、exact-head cloud分開記錄。
`--no-verify`與原default掃描的1338 tuples已驗相同，見 [一致性](noverify-equality.json)。

## 邊界與回退

helper驗證收到的報告；若scanner完全漏報整份檔案，仍屬原scanner信任邊界，不能把本修復稱為掃描完整性證明。
原空report與六pins語意保持。新例外僅能用於已審核且未改的13個不可變歷史檔案。

回退只撤本卡helper hunks與新tests；保留全部快照、原Git歷史及其他工作，沒有DB／runtime migration。
回退會恢復已知誤報。owned clone僅複製HEAD與本卡兩份程式，未納入並行UI／startup修正或私人資料。
owned候選已移除，原工作區與其他程序保持；各檢查及清理的最終結果見 `FINAL_RESULTS.json`；尚未完成的remote check不得以local PASS代稱。
