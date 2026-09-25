# T10 Evidence

- Date/profile: 2026-09-24, local loopback gateway L2.
- Versions: FastAPI 0.141.1, Starlette 1.7.0, Uvicorn 0.53.0, websockets 16.1.1.
- Command: `scripts/check`; `uv run siro-gateway`; browser walkthrough at `http://127.0.0.1:8000`.
- Actual: loopback-only short session bootstrap, bearer-protected snapshot and mutations, Origin-checked WebSocket authentication, per-client urgent/normal bounded queues, exactly one writer task per socket, snapshot reconnect, turn/cancel events, health/routes, and local kill switches. A blocked client is removed without delaying a fast client; 50 concurrent producers preserve one socket writer; 100 reconnects leave zero clients/tasks.
- Browser QA: the page rendered identity/health/routes/switches, established an authenticated control socket, and emitted a `turn_started` event from a typed message. Closing the real browser exposed a duplicate-close cleanup error; the close path is now idempotent with a regression test.
- Evidence: `tests/integration/test_gateway.py`, `src/siro/services/presentation/gateway.py`, `src/siro/services/presentation/static/index.html`.
- A05/A06: PASS at local L2.
- Result: PASS.
