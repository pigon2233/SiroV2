# T08 Evidence

- Date/profile: 2026-09-23, persistent offline L1.
- Command: `scripts/check`; run the demo twice against the same temporary data directory.
- Actual: bounded session-scoped working memory, identity prompt assembly, source-backed episodic retrieval, owner-editable persona, durable conversation, and one-command offline demo work. A memory is recovered with its event source after three store restarts; changing adapters keeps `identity_id`; missing evidence produces an explicit unknown answer.
- A03: L1 PASS；T07 已補 Groq/Ollama 兩個真 backend 的 identity 不變證據。
- Evidence: `tests/integration/test_persistent_companion.py`, `src/siro/core/memory.py`, `src/siro/core/companion.py`, `src/siro/cli.py`.
- Result: PASS for offline P1 core; real-backend evidence pending external access.
