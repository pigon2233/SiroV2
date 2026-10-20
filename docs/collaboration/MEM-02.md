# MEM-02 認領

2026-10-20 Asia/Taipei；Codex；PARTIAL／DETERMINISTIC_GATES_LOCAL_VERIFIED／REAL_MODEL_FAILED_VERIFICATION／LOCAL_ONLY／NOT PUSHED。
使用者持續目標「一直做下去」，延續MEM01後的整個記憶計畫，不以本卡取代全目標。
Base 259fddacb9c585de3c5c4a7ae3ac6a111539cd00；branch codex/memory-mem02-20261020；
worktree E:/coding/股票策略機器學習/SiroV2-mem02-20261020。
Owned paths：src/siro/core/{context.py,companion.py,conversation.py,memory.py}、
src/siro/persistence/memory.py、tests/integration/test_context_understanding.py、
tests/fixtures/context_understanding.json、scripts/evaluate_context_understanding.py、
docs/DECISIONS.md D77附錄、docs/CONTRACTS.md附錄、docs/memory-evolution/PLAN.md、
docs/evidence/MEM-02-20261020/、本檔。
不改Gateway/static/音訊/renderer/依賴/lockfile/schema；原checkout的8個語音dirty檔保留。
共享STATUS留整合者由本報告納入。Git fetch成功，issues/pulls公開API空陣列；修改前再查。
本機紀錄不是共享鎖；無遠端認領，不push、不PR、不部署、不讀私人對話DB。

目標：typed/data-only上下文、中文／追問的有界語境檢索、短期privacy隔離、
pre-dispatch來源重驗、原native history/pending tools不裁改。接現有Core caller，無第二planner或memory store。
固定30組合成多輪資料，確定性capture與來源/授權硬gate；語義模型評測單獨報，不把mock答案算理解。
驗收：來源更正/撤銷在checkpoint與dispatch間變更時零provider dispatch、cloud不含local資料、
原cancel/session restore/context budget/native tools相鄰回歸。真provider只用合成資料與已有授權profile，
若缺配置或quota誠實保留語義gate，繼續其他可執行工作，不自造綠燈。

結果：Core接線／來源fence與30case capture已驗，114回歸＋44專項＋5switch通過（有重疊）。
模型27/30未跑；見 ../evidence/MEM-02-20261020/REPORT.md。持續目標active，不重定義完成。

續作：2026-10-20，基線1a45022；修正真模型聚合讓29/30掩蓋虛構授權／錯報完成的漏洞。
認領路徑不擴張；遠端issues/pulls空、fetch已查，原八個dirty檔保留。
新增五反例、整檔49 PASS；capture30/30、real仍BLOCKED_CONFIG；報告有可重現證據。
依原零越權要求明訂獨立semantic hard gate，不降低27/30理解目標。LOCAL_ONLY／NOT PUSHED。

使用者要求查運行中的模型後，找到WSL PID807實際設定qwen3:4b-instruct、Ollama11434。
缺模型判斷更正：漏查程序環境，不是確實沒有模型。沿用現有模型完成首次30case真評測，
capture30/30、自動語義22/30；人工發現C22自然語言錯報測試通過而布林false，不能宣稱零錯報。
同工作區／分支，基線b2c01dc；本輪只更動本交接、PLAN、REPORT與本任務evidence目錄。
模型metadata與合成真回答已留證，不含密鑰、未改使用中服務／私人DB／其他owner檔案。

續作基線66c8ced：檢查既有模型template與最小多輪診斷；只在原owned context.py與評測／
測試／本交接／PLAN／CONTRACTS／本任務evidence範圍修正。固定30fixture與27門檻不改。
對話template不擅自修改，另裝的qwen3:4b只作對照診斷，不替換正式或評測所選模型。
逐題檢查新批次自然語言，不把model自報布林當安全證明。GitHub唯讀查詢與dirty已再核對。

結果：繁中context policy＋評測格式修正；最終62回歸PASS，真模型25/30未過27。
本輪三個30case批次22/25/25均留證，逐題正文審閱有角色錯置／虛構自己手動檢查的缺口。
MEM02保持FAILED_VERIFICATION／PARTIAL；不是模型配置阻礙，不標整個goal完成或blocked。
未改fixture／expected、模型設定、其他owner範圍，未push／PR／部署。完整命令與限制見REPORT續作。

續作基線5e0016ed31ccc772e47d5a9ab7fa96d1ba124339：原owned core/memory.py、context.py、
persistence/memory.py、context integration tests、CONTRACTS／D77附錄、PLAN與本evidence內
補來源event type的原子metadata與呈現；不改schema／依賴／Gateway／native message內容。
source type只表示事件類別，不等於已驗owner身份、事實或成功readback。舊snapshot保留未知。
新增metadata採用／dispatch都重驗，固定30fixture與門檻不改；遠端／本機dirty已再查。

結果：來源event metadata原子capture／preflight／adoption與context角色已接，129回歸PASS。
同一真模型新批次25/30，完整正文審閱23符合／7有缺口，仍FAILED_VERIFICATION／PARTIAL。
未改評測器、fixture或模型，未push／PR／部署。新程式與所有實測結果由本輪本機commit保存。
