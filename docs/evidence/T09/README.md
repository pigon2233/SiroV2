# T09 Evidence

- Date/profile: 2026-09-24, local NATS JetStream L2.
- Versions: `nats-server 2.15.0`, `nats-py 2.16.0`, SQLite migration 4.
- Command: `scripts/check`.
- Actual: a real ephemeral JetStream server receives SQLite outbox delivery; a consumer crash after DB commit and before ack causes redelivery, while the inbox ledger keeps the committed side effect count at one. A disconnected broker leaves the event pending, bounded failures move it to quarantine, and replay projects stored events while the replay runtime rejects side effects.
- CI: installs the pinned NATS server and runs the same integration tests.
- Evidence: `tests/integration/test_nats_delivery.py`, `src/siro/events/nats.py`, `src/siro/events/replay.py`, `config/nats-server.conf`.
- A04: PASS at L2 for publish/redelivery/dedup/replay safety.
- Result: PASS.
