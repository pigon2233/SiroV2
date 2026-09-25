# T07 Evidence

- Date/profile: 2026-09-23, adapter contract L1.
- Command: `scripts/check`.
- Actual: OpenAI-compatible and Ollama adapters share the model port, map text/tool/usage, honor cancellation and timeout, constrain output budget, start a new provider generation on failover only before visible text, and deny cloud egress unless privacy is `cloud_allowed`.
- Evidence: `tests/contract/test_model_adapters.py`, opt-in `tests/real/test_model_providers.py`, `config/models.example.env`.
- Real local integration: PASS. Official Ollama 0.34.3 user-local install, persistent loopback user service, and `qwen3:4b` Q4_K_M completed the real adapter test. The first request exposed empty content when the thinking budget consumed all 16 tokens; adding `think: false` fixed the production adapter, and the warm rerun completed in 0.48 seconds (test suite) and then 8.30 seconds after service restart/model reload.
- Cloud integration: PASS using Groq's OpenAI-compatible endpoint and `openai/gpt-oss-20b`. The credential is stored only in ignored mode-600 `.env.local`. A real request exposed that generic Python `urllib` was rejected until the adapter supplied an explicit user agent; the production transport now includes one. No private SIRO data was used.
- A03 real backend swap: PASS. A synthetic identity answered once through Groq and once through Ollama against the same SQLite store; `identity_id` and immutable core remained equal afterward.
- Command: `SIRO_RUN_REAL_PROVIDERS=1 SIRO_OLLAMA_MODEL=qwen3:4b uv run pytest -m real_provider tests/real/test_model_providers.py -vv` after loading the ignored local environment.
- Actual: 3 real tests passed in 15.38 seconds.
- Result: implementation/L1 PASS; Groq L2 PASS; Ollama L2 PASS; two-real-backend A03 PASS.
