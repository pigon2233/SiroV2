# T04 驗收證據

日期：2026-09-23｜結果：PASS｜層級：L1/L2 本機 SQLite 整合

## 交付

- `src/siro/ports/persistence.py`：transaction、event/outbox、inbox、backup/restore port。
- `src/siro/persistence/sqlite.py`：asyncio thread offload、single-writer lock、WAL、foreign keys、migration checksum。
- migrations `001_events.sql`、`002_domain.sql`：CONTRACTS 的核心資料表與索引。
- `tests/integration/test_sqlite_store.py`：初始化/升級、原子性、去重、rollback、backup/restore、路徑錯誤。

## 驗收結果

```text
scripts/check
42 files already formatted
All checks passed!
Success: no issues found in 22 source files
31 passed in 1.89s
```

已驗證：空 DB 建立 version 1→2、WAL、store connection foreign keys、migration checksum 防竄改、event+outbox 同 transaction、duplicate event 不建立第二份 outbox、inbox consumer work 失敗時 marker 一起 rollback、第二次成功只處理一次、consistent backup、修改後 restore 回備份狀態、integrity check、無法使用的 parent path 明確失敗。

## 限制

- 所有 blocking SQLite/backup 工作以 `asyncio.to_thread` 執行；目前每次操作開 connection，由 asyncio lock 保持主要寫入序列化。
- inbox/outbox 已提供本機一致性；broker dispatcher、ack/redelivery/quarantine 屬 T09。
- migration SQL splitter 刻意只支援不含 trigger 或字串內 semicolon 的 migration；若日後需要，先替換可靠 parser/runner 並補 migration rollback tests。
- Backup 未包含 secret store；正式 retention/encryption/CLI 到 T34。
