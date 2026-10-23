# T18／T30 驗證、修復與檢視入口

2026-10-20 Asia/Taipei；MEMORY-T18-T30。既有元件缺陷修復 LOCAL_VERIFIED；
產品完整接線 PARTIAL／WAITING_OWNER_HANDOFF；未推送、未部署、未啟用自動寫入。

## 本輪實際發現

原T18/T30六個測試全部PASS，但不覆蓋以下邊界。第一輪新增反例7 FAIL／1 PASS；
第二輪identity反例2 FAIL／8 PASS；總共重現9個不同缺陷，不把舊卡DONE當成零缺陷。

| 任務 | 重現的缺陷 | 實作 |
| --- | --- | --- |
| T18 | 同run key可換identity繼續 | start/resume核對原owner，不改row |
| T18 | trait可引用不存在的三個event | 同transaction驗證真來源才更新projection |
| T18 | 重複source ID在start後才失敗並留下run | candidate建立時先拒絕非獨立來源 |
| T18 | 直接commit可寫到其他run的identity | 寫入交易先驗run owner |
| T18 | 相同候選會跨identity誤去重 | 去重查owner；原key碰撞時使用scoped key，單identity沿用舊key |
| T30 | 同一trace UUID重播可當兩次成功 | 拒絕duplicate_trace，不產生候選 |
| T30 | list/tuple內dict與字串secret未脫敏 | argument/result遞迴遍歷容器，沿用既有secret pattern |
| T30 | 候選model能宣稱enabled | Literal candidate，與既有DB CHECK一致 |
| T30 | 同workflow重新保存撞unique key | 指定workflow_hash conflict保持首份審閱資料，其他約束錯誤不吞 |

Relationship來源拒絕原本就正確，新增回歸保留；沒有重寫這段。
既有run的原candidate key仍可讀取去重；新增單identity仍寫原格式，避免一般code rollback後重複記憶。
跨identity collision才用新key；這是資料隔離保護，不代表新建多使用者產品。

## 已新增的可執行入口

scripts/review_memory_candidates.py：對明確指定的本機DB，以mode=ro/query_only查詢
有界T18 run／T30 candidate metadata，預設各20、最多100，回報has_more。
不migrate、不寫記憶、不enable/install，不輸出fixture／記憶原文／source IDs／run key／capability名稱。
不查skill registry，因此installation_status=not_checked，不假稱從候選資料就能知道安裝狀態。

```sh
python scripts/review_memory_candidates.py --database /path/to/authorized-siro.sqlite --limit 20
```

只有操作者明確指定的DB才讀取；本輪僅使用暫存合成DB，未使用上方範例讀私人資料。
missing/legacy/不相容DB或無效limit退出2且不建DB；成功回JSON，退出0。
這是metadata檢視入口，不是完整候選審閱／批准產品，也不是T18自動排程接線。
真CLI子程序、中文／空白路徑、查詢前後DB主檔hash不變、無原文輸出均由測試驗證。
查詢可能使用SQLite WAL／SHM正常機制，主檔不變不代表完全無檔案系統輔助動作。

## 版本與驗證命令

Worktree E:/coding/股票策略機器學習/SiroV2-memory-20261020。
Branch codex/memory-t18-t30-20261020。
Base b880ae9ec570d11fc5bb905c835d43445a2c6d13，產品來源origin/main 137a561。
原checkout在claude/vrm-renderer-m1，有語音常駐worker／串流朗讀相關8個dirty檔，未接手或改寫。
公開GitHub issues/pulls查詢皆空陣列、fetch成功；沒有遠端認領，本機文件不是共享鎖。

WSL，既有ext4 Python3.14.4／pytest9.1.1，無安裝／下載。從本worktree執行：

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /home/pepepig/.local/share/siro/venv/bin/python \
  scripts/run_acceptance.py tests/integration/test_consolidation.py \
  tests/integration/test_procedural_candidates.py tests/integration/test_memory_learning_guards.py \
  tests/integration/test_memory_candidate_review.py tests/integration/test_memory_v2.py \
  tests/integration/test_memory_organization.py tests/integration/test_memory_ingress.py \
  tests/contract/test_boundaries.py --level L1 --git-executable git.exe \
  --output /tmp/siro-memory-T18-T30-final-20261020-01
```

結果：41 PASS／0 SKIP／7既有warnings，36.54s，runner退出0、source前後hash相同。
重現時用新的output目錄。receipt.json為該次實際結果，base＋dirty來源；
完成後只加了合成secret的精確scanner allowlist註解與交接/證據文字，未再改執行邏輯。
舊core crash子程序／真SQLite／ASGI主程式使用合成模型；不宣稱真provider或真人記憶品質。
12項新guard＋7項新CLI測試與22項既有回歸合計41；不重複加總較早的6/14/20/39PASS。

Ruff check與format check：本次7個Python檔PASS；mypy同7檔PASS。
明確掃描同7檔detect-secrets＋scripts/check_secrets.py PASS；
首輪只標到合成sentinel賦值，精確allowlist該行後通過，沒有放寬全域規則。
新測試一處lambda型別推斷修成單次executemany；最終type檢查通過。
git diff/staged diff --check通過。完整scripts/check、雲端CI、真硬體／真人／正式部署rollback未跑。

## 現有產品缺口（仍未完成）

- T18 consolidator仍是給定候選的library；Gateway只啟用RT015唯讀MemoryOrganizer。
  沒有把Dream候選自動升格為facts/traits，來源數不能當事實正確證明。
- T18同run key還未綁完整輸入批次／順序fingerprint，parent memory revision撤銷與
  trait/relationship同證據重試冪等，仍是自動化前的gate，見PLAN MEM01/MEM05。
- T30仍無可信terminal trace feed／使用者完整審閱介面；trusted布林不能由模型自行提供。
  目前workflow signature只有capability＋argument keys，不是語義參數化。
- T30 unique workflow key未分identity/person，v1單owner範圍不自動擴成跨scope學習；
  不累加來源或覆寫首份fixture，後續需typed template與scope設計再接trace feed。
- Gateway與HTML被其他進行中工作占用，沒有owner移交，不跨檔搶寫；此狀態不標整卡DONE。

後續上下文／自動記憶／主動記憶計畫在 ../../memory-evolution/PLAN.md，全部標PLANNED。
共享STATUS/DECISIONS/roadmap由整合者根據本報告與決策文件更新；本輪不覆寫共享進度。

## 回退與交接

來源修復可在本分支revert本輪commit；先停任何接入本library的producer，保留最新DB與revisions。
沒有schema migration，也沒有改已存在的memory/output。
單owner key保持舊格式；多identity collision資料使用舊程式仍可能回到原跨identity去重缺陷，
因此有此資料時不得以舊library做多identity學習；不能靠還原舊DB消掉最新記憶。
沒有做正式部署回退演練，以上是source回退範圍。
交付commit SHA由最終回覆與git log提供，不在本檔自引用；NOT PUSHED，不自行merge。
