# T06 Evidence

- Date/profile: 2026-09-23, local deterministic L1.
- Command: `scripts/check` and `uv run siro demo --data <temp> --once '你記得嗎？'`.
- Actual: ordered streaming completion with one trace and one terminal signal, explicit cancellation, new-input cancellation, late-chunk isolation, timeout terminal state, durable messages, and 100 generation races pass.
- A01/A02: L1 PASS. A01 L2 provider evidence remains part of T07 external verification.
- Evidence: `tests/integration/test_conversation.py`, `src/siro/cli.py`.
- Result: PASS for T06 mock/offline scope.
