# T03 驗收證據

日期：2026-09-23｜結果：PASS｜層級：L1 deterministic async tests

## 交付

- `src/siro/ports/events.py`：Clock、EventBus、Subscription、PublishResult、DeliveryStats、BusSnapshot ports。
- `src/siro/events/local.py`：本機 bounded priority bus、獨立 subscriber worker、TTL、dedup、cleanup。
- `tests/test_local_event_bus.py`：壓力、隔離、優先級、公平、失敗、unsubscribe/stop 測試。
- `pytest-asyncio` 鎖入 dev dependency，strict asyncio mode。

## 行為證據

- 10,000 個 telemetry events、subscription capacity 32、dedup capacity 128：pending 不超過 32，dedup 固定 128，滿載以明確 eviction 統計呈現。
- slow subscriber capacity 1 與 fast subscriber capacity 32 同時接收：fast 完整取得 20 個事件；slow 的拒絕不阻塞 publish 或 fast worker。
- urgent 會淘汰較低 priority；連續 8 個 urgent 後讓 background 前進，避免永久飢餓。
- 同 event_id 第二次 publish 標記 duplicate；超過 received_at + ttl 的事件標記 expired；兩者皆不交付。
- handler 第一次丟例外後 worker 保持可用，下一事件仍完成；failure 有統計。
- unsubscribe 後 worker 數下降；stop 後 subscriptions/worker_tasks 均為 0。

## 完整檢查

```text
scripts/check
37 files already formatted
All checks passed!
Success: no issues found in 18 source files
24 passed in 1.81s
schema --check: pass
secret scan: no findings
```

## 設計限制

- 這是單一 asyncio event loop 內的 bus；不支援 thread-safe publish 或跨程序 durability。T09 另接 NATS/JetStream。
- dedup 是有界記憶窗口，不取代 T04 inbox/outbox 或 action idempotency ledger。
- ephemeral background/telemetry 滿載時可淘汰；interactive/urgent 無較低 priority 可淘汰時會明確 rejected，producer 必須處理結果。
- Local bus 不做 durable replay，符合 CONTRACTS 將 durable mutation 交給 SQLite outbox 的責任分界。
