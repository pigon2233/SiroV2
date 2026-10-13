# RT-004 verification findings 修正 — 2026-10-01

原因：Gateway computer.execute 每次dispatch讀 mutable os.environ，controller只在建立時讀，兩者可能不一致。最小修正：main組裝前讀一次runtime_profile，executor closure與IntegratedCompanion共用該值。profile在此Gateway instance生命週期固定（比每run固定更強）；新profile需排空後重啟，不提供熱切換API。

Production只改gateway.py：新增startup profile捕捉、dispatch改用捕捉值、controller用同一值；沒有RT-005/process-tree功能、授權/HTTP/schema/音色更動。保留其他dirty變更。

Tests：原main測試擴為兩profile×是否中途改env，共4cases。AsyncMock(wraps=real helper)只觀測binding，仍執行真子程序；provider/uvicorn server仍synthetic，HTTP/Core/SQLite/orchestrator真。修正前兩個mutation cases皆FAIL（legacy錯用candidate、candidate錯用legacy）；修正後皆PASS。timeout child寫PID，回傳TimeoutError後assert /proc/PID消失，涵蓋silent/flood。

RT-003既有test改名orderings，加入completion-first；100cancel-first+100completion-first皆驗一次terminal、無terminal後工具/delta事件、正確DB終止state，並驗後續dispatch數。不是200種隨機race，也不宣稱任意await點窮舉。没有RT-003 production修改。

驗證命令與結果：
- `.venv/bin/pytest -q tests/integration/test_bounded_execution.py tests/integration/test_gateway_main.py tests/integration/test_gateway.py tests/integration/test_agent_batches.py tests/integration/test_integrated_companion.py tests/integration/test_computer_driver.py`：43 passed，19.23s，exit0（在orderings測試擴充前執行）。
- 最後RT-003測試修改後 `.venv/bin/pytest -q tests/integration/test_agent_batches.py`：8 passed，22.22s，exit0，包含上述200iterations。
- `.venv/bin/pytest -q tests/integration/test_sqlite_store.py tests/integration/test_conversation.py tests/integration/test_persistent_companion.py tests/contract/test_model_adapters.py tests/test_affect.py tests/test_affect_simulation.py tests/integration/test_relationships.py tests/integration/test_identity_world.py tests/integration/test_memory_v2.py tests/integration/test_affect_persistence.py tests/integration/test_affect_outcomes.py tests/integration/test_body_failure_isolation.py tests/contract/test_body_adapter.py tests/contract/test_body_assets.py`：69 passed，9.65s，exit0。
- `.venv/bin/ruff check src tests` PASS；`.venv/bin/mypy` PASS，167files；三个changed source/test format check PASS。

各套件無skip/xfail，dependency deprecation warnings仍存在。未跑全套；不將重疊cases相加宣稱distinct總數。100MiB RSS/body/memory/relationship等相關fixtures通過；真provider/GPU/GUI/部署rollback仍未測。

舊verification報告保留為修正前歷史；verification/profile_probe.py透過改寫當時test重現舊bug，已被正式4case回歸取代，不以其動態改寫當前測試的結果判定修後狀態。原source digests保留，修後新增此目錄digests，預期舊gateway/test hash drift。

Acceptance修後：candidate/legacy兩方向profile freeze PASS；有界輸出與既有觀測PASS；timeout直接child reap PASS；batch兩種終止順序PASS。RT-004保留DONE並附repair evidence，不改寫歷史PARTIAL報告。

Remaining：process tree/run cancel RT-005、durable recovery RT-008、長sessionguard retention、真服務/部署rollback及隨機race仍未完整驗證。沒有為降低風險而新增功能，也未以此宣稱產品完成。

Rollback：排空jobs後可撤回本次gateway三處profile捕捉修改與測試/doc增量，保留原RT/dirty工作；但會恢復已知profile問題。正常操作rollback仍排空後重啟legacy，禁止server內env熱切換與重播副作用。
