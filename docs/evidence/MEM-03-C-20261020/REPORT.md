# MEM-03-C：持久候選與明確審閱後端

2026-10-20 Asia/Taipei，base96cd2e21194d6c47a0d6cdc0906c7e68d622e362，
branch codex/memory-mem03-review-20261020，managed worktree
E:/coding/Worktrees/memory-mem03-review/SiroV2。LOCAL_VERIFIED（L1組件）／NOT_WIRED／LOCAL_ONLY／NOT PUSHED。

## 行為與資料

沿用既有Memory／candidate status／revision／FTS，新增Core review service、SQLite repository與
migration017的review metadata／action ledger。沒有第二MemoryStore，也沒有修改舊migration。
來源層原本的SQL檢查提成同transaction inspect helper；唯讀prepare仍設定query_only，
writer只在已取得交易鎖後重用同一組來源／人物／identity／TTL／privacy／撤銷／hash檢查。

stage的文字由A/B依已保存UUID取得，先候選不進recall／FTS；approve才轉committed與索引，
仍標episodic使用者陳述，不自證工具readback或semantic fact。reject／withdraw留deleted revision，
失效／過期待審項仍可用實際revision撤回，不能批准或重新自動回填。編輯需新可信owner event，
同交易撤回舊candidate、插入新candidate並帶replaces ID；沒有直接接受caller文字替換來源。
批准保存期由可信permit明示，仍受原source TTL上限；pending保留24h與source TTL較早值。
沒有物理purge，不能說刪除已清空舊頁／revision／備份。

獨立Policy lease port預設拒絕，來源allow_preparation不是寫入grant。lease必須將review與
相關SourcePolicy修改序列化，持有到SQL worker結束；無正式adapter就不能裝配writer。
這是可信應用介面，不是新Policy engine或由事件旗標產生的授權；沒有真auth／Runtime／Gateway
整合證據。來源producer／本機DB信任限制沿A契約，沒有新增對惡意本機任意DB writer的防護宣稱。

操作帶UUID、完整命令hash與expected revision，Memory／FTS／review state／action ledger同交易。
同命令重送只查已提交state_at_commit，不冒稱是當下狀態；同UUID改參數拒絕。metadata list／
lookup限scope與kind，preview另重驗來源／Policy，repr不含私有文字。讀取錯誤用固定訊息的
ReviewReadUnavailable區分於空清單，避免UI將故障說成沒有記憶；完整物件仍不可asdict後記log。

SQLiteStore.to_thread一旦開始寫入，取消會shield＋join至terminal，再釋放lease並向caller傳遞取消。
caller用原action UUID查結果，不能因timeout／取消盲重送。DB故障回unknown，不假稱沒有發生。
測試確認取消期間Policy修改仍等候lease，transaction完成後才允許修改；取消的批准可由ledger查明。
這不代表已完成未來background single-owner／批次producer／foreground job搶占整合。

## 驗證結果

最終[receipt](regression-receipt.json)：**411 PASS／0 FAIL／0 SKIP**，pytest54.28秒、
receipt55.855秒，source before/after一致。包含本卡44專項、A/B來源及內容、MEM01 lineage、
RT014入口、Memory v2、上下文契約、邊界、SQLite交易／備份／restore／cleanup及ReleaseManager。
這是合成資料＋真SQLite的L1，Policy為測試lease，沒有真provider／真人／硬體L3。

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src PYTEST_ADDOPTS='-o cache_dir=/tmp/siro-mem03c-regression-cache' /home/pepepig/.local/share/siro/venv/bin/python scripts/run_acceptance.py --output /tmp/siro-mem03c-final-regression-20261020 --level L1 --git-executable git.exe tests/integration/test_memory_review.py tests/integration/test_memory_candidates.py tests/integration/test_memory_source_gate.py tests/integration/test_memory_derivation_bindings.py tests/integration/test_memory_ingress.py tests/integration/test_memory_v2.py tests/integration/test_context_understanding.py tests/contract/test_boundaries.py tests/integration/test_sqlite_store.py tests/integration/test_sqlite_backup_lifecycle.py tests/integration/test_sqlite_restore_validation.py tests/integration/test_sqlite_restore_lifecycle.py tests/integration/test_sqlite_connection_cleanup.py tests/integration/test_release_manager.py
```

44專項包括：重啟重建／preview／approve／no pending FTS、local資料不進cloud recall、reject／
withdraw／new-owner-event edit、kind／actor／scope／auth／ASK／期限拒絕、來源更正／撤銷／
row hash／TTL／Policy revision、Core preflight後的DB競態、CAS／並發／完整命令hash、ledger故障
整體DB hash不變、取消兩次仍join、permit於transaction結尾過期回滾、read故障脫敏、
15→17保留真舊資料與衍生邊／checksums、16→17／重啟／FK、失敗migration17回退到16，
批准後correct／delete／revoke仍使MEM01衍生物失效，expired／invalidated待審項可以撤回。

進程內兩個/tmp pytest plugin mutants：繞過transaction source binding→source hash／identity
兩負例FAIL；取消時直接丟下worker→join負例FAIL，均0 error／skip。mutation-results.json保留
plugin與targets，可寫到臨時mem03c_mutant.py，用PYTHONPATH加臨時目錄及-p mem03c_mutant重現。
沒有修改repo source或保存原文stdout／JUnit；只證能抓這兩種故障，不是完整mutation coverage。

早期collection ERROR是persistence新模組尚不存在；首批27 PASS。新migration故障測試一度
誤期待MigrationError，實際既有apply_migrations會傳sqlite3.OperationalError，測試已核對修正，
沒有為此改舊SQLiteStore。之後35 PASS；新增撤銷後withdraw反例先FAIL（CONFLICT），發現舊guard
連已失效待審項也拒絕移除；修正為同scope／實際revision可移除，批准仍要求完整有效綁定。

首次廣回歸410 PASS／1 FAIL保留early-regression-receipt.json：舊升級fixture用migrations[:-1]
會隨新增migration漂移成schema16，且斷言仍只預期16。改明確migrations[:15]、驗15個舊checksums
不變及新增[16,17]，保留原資料／衍生邊與更正後失效檢查；舊release測試改用實際最新schema，
不是用current_schema16先攔住17而誤稱驗到了manifest上限。合成max_schema15／16仍拒絕17，
未讀取或宣稱知道live release manifest上限，沒有放寬發布檢查。

Ruff check／format、五個相關Python檔mypy、event schema export --check PASS；static-checks.json
記本卡十個新增／修改路徑detect-secrets scan與既有checker均退出0、零finding。沒有新增依賴，
使用既有WSL ext4 Python3.14.4／pytest9.1.1與/tmp caches，未pip／uv同步。
未跑全庫scripts/check／全庫mypy／全庫secret掃描；B報告的全庫未解finding未解除，不能拿本卡
scoped scan當全庫通過。相鄰套件七個既有warnings保留，沒有安裝可選套件或關閉警告。

## 限制與下一步

MEM02模型理解仍25/30未過27，主MEM03及原持續目標未完成。UI、可信owner marker入口、
真Policy lease adapter、按類型opt-in／retention／purge、單background owner／batch100／60秒／
foreground cancel-join、完整語義與真人誤記率仍待交付。B的規則不是通用DLP，不能因本卡能
保存candidate就啟用自動持久化；本輪只用合成DB，沒有遷移私人DB或改運行服務。

共享STATUS／PLAN未取得整合owner，按協作規則交本卡報告由整合者更新；原checkout已由其他工作
前進至babfeddc07851c6ec4030c2a186f42c4e75a6660，本卡未切換／覆寫／混入那些成果。
回退不能降版覆蓋schema17資料：關閉新caller（目前無正式caller），保留既有Memory與review表，
由支援該schema的版本讀取或做另行設計的資料遷移。舊schema上限的release應拒絕此DB。
所有成果只本機commit，完整SHA由最終git log／回覆給出，未push／PR／merge／部署。
