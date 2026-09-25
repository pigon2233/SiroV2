# T05 Evidence

- Date/profile: 2026-09-23, local deterministic L1.
- Command: `scripts/check`.
- Actual: identity core requires explicit owner authorization; traits retain revisions and sources; identity survives restart; world current projection rejects older observations and returns unknown after TTL.
- Evidence: `tests/integration/test_identity_world.py`.
- Result: PASS.
