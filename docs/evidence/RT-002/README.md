# RT-002 completion / 2026-10-01

Selected: RT-002，第一個未完成且 dependency RT-001 DONE 的 task。只完成本卡。

## Changed files

- src/siro/core/conversation.py：optional messages → ModelRequest。
- src/siro/core/companion.py：optional per-run message_history；首次 context/system + original user，續作不重做 memory query、不加入 user working memory；append assistant call。
- src/siro/services/presentation/integrated.py：candidate run history + call_id tool result，terminal/limit 清理；history 缺失拒絕假恢復。
- src/siro/services/presentation/gateway.py：主入口 SIRO_RUNTIME_PROFILE（legacy default）傳入 controller。
- tests/integration/test_integrated_companion.py：真 Core/SQLite/OpenAI adapter + synthetic transport，兩輪工具 payload、原目標、角色配對、tool內容隔離、新run清理驗證。
- docs/DECISIONS.md、docs/CONTRACTS.md、docs/STATUS.md、roadmap 與本證據。

ModelMessage/serializer 在稽核前已存在，與 task 描述一致；本卡未重寫 adapter。gateway main composition 需增一個 optional env profile，屬相容計畫既定範圍；未改 JSON config/HTTP/WS/state format。沒有修改 memory/identity schema、body/audio。

## Tests

- 首輪相關 tests：21 passed（integrated_companion、conversation、persistent_companion、model_adapters）。
- 全套 uv run pytest -q：199 passed、5 skipped，21.21s，exit 0。
- 最後 history-limit cleanup/continuation audit prompt 改動後：test_integrated_companion 5 passed，exit 0。
- uv run ruff check src tests：PASS；uv run mypy：PASS（164 files）；受影響 Core/Integrated format check PASS。
- 5 real-provider/speech opt-in tests skip；transport payload integration 為 synthetic，未宣稱真雲端/GPU/硬體驗收。

Acceptance：原 user goal 在兩個工具round後不變；assistant call ID 與 tool response相同；工具內容留 tool role且不寫成 user utterance；舊legacy fixtures全套仍通過。現有 body/affect/relationship測試保留通過。

Limitations：history僅RAM、重啟不可續native run（RT-008）；同批多tool時序仍屬RT-003；取消完整傳播另卡。candidate為opt-in，legacy default。無架構搬移、無新增migration；不得以此卡宣稱整體runtime完成。

Rollback：排空當前candidate run，再以 SIRO_RUNTIME_PROFILE=legacy啟動新runs；不要途中切換或重播副作用。需要撤回source時只撤本卡optional passthrough/profile變更，保留既有dirty tree。
