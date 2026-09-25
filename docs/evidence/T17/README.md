# T17 驗收證據

日期：2026-09-24

## 產出

- `MemoryKind` 明確區分 Working、Episodic、Semantic、Procedural、Self；Working 保持 session-scoped bounded memory，其餘持久化到 SQLite。
- migration 005 新增 person scope、revision history 與 FTS5 index。
- recall 在 identity/person scope 內才做檢索，支援 kind、有效時間、source event 與 limit。
- semantic facts 保留 subject/predicate 相同但 value/verification 不同的衝突記錄，不靜默覆蓋。
- owner correction 建立新 revision 並加入更正來源；owner deletion 標記 tombstone、移出 FTS，遞迴撤銷 derived memory。
- 認證 API 提供 browse/search、revision inspection、correction 與 deletion。

## A10

固定 20 組 semantic target，每組混入 3 個相似 episodic distractor。逐組查詢 top-5，20/20 命中帶正確 source 的 target，高於 18/20 門檻。資料完全合成且 deterministic。

## A11

- 更正 `favorite color is red` 為 blue 後，舊文字不再被 recall，兩版與兩個 source 都可檢查。
- 刪除來源 memory 後，其 derived self-summary 同時不可檢索。
- FTS rebuild 不復活 deleted memory。
- SQLite consistent backup/restore 後 deletion 仍成立，backup 之後的暫存 memory 不存在。
- owner/guest 與不同 identity fixtures 不互漏。

## Gate

```text
scripts/check
66 passed, 3 skipped (real providers require explicit opt-in), 1 dependency deprecation warning
```

這是 L1 合成資料與真 SQLite/FTS/HTTP ASGI integration；不使用 embedding，也不宣稱語意向量召回品質。
