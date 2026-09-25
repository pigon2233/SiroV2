# T02 驗收證據

日期：2026-09-23｜結果：PASS｜層級：L1 deterministic contract tests

## 交付

- `src/siro/contracts/events.py`：64 KiB 有界、v1 envelope、9 類型化事件、discriminated validation、timezone/session rules。
- `src/siro/contracts/boundaries.py`：Core 禁止依賴 adapters/services/runtime 的 AST 檢查。
- `schemas/events/event.v1.schema.json`：由 Pydantic contract 決定性產生的跨語言 JSON Schema。
- `scripts/export_schemas`：產生與 `--check` stale detection。
- `tests/fixtures/events`：合法、缺必要欄位、未知 schema version golden fixtures。
- `tests/contract`：事件大小/type/time/session/schema 與 dependency boundary tests。

## 執行結果

```text
scripts/check
31 files already formatted
All checks passed!
Success: no issues found in 13 source files
17 passed in 0.18s
schema --check: pass
secret scan: no findings
```

驗證涵蓋：合法 user text、缺 source、未知主要版本、未知 event type、超過 64 KiB、naive timestamp、跨 session causation、discriminator mapping、UUID parsing，以及用合成壞 import 證明 boundary checker 會失敗。

## 限制與後續

- CONTRACTS 目錄中的其餘事件會在實際 producer/consumer 任務加入；本次完成「首批事件」，沒有宣稱全部未來 payload 已凍結。
- 目前 schema 只有 Python 產生與測試；T10/T13 才加入 TypeScript/binary audio golden fixtures，T21 加 Rust client。
- 事件 transport、backpressure 與 subscriber lifecycle 屬 T03，尚未實作。
