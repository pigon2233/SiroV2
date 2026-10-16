# Bounded rate-limit recovery — 2026-10-16

## Scope and implementation

Only `src/siro/adapters/models/failover.py` and the new
`tests/contract/test_rate_limit_recovery.py` are owned by this subtask. Gateway,
UI, Core, ports, DB, tools, speech and runtime workers are unchanged by this
subtask. Product composition and visible retry notification are verified
separately by the root task.

New optional constructor arguments:

```python
rate_limit_max_wait_seconds: float | None = None
clock: Callable[[], datetime] | None = None
on_retry: Callable[[ModelRequest, float], Awaitable[None]] | None = None
```

`None` preserves the existing retry/fallback policy. An explicitly configured,
finite cap in [0, 60] enables Retry-After handling for HTTP 429. Recovery retains
the selected provider and the original request messages, output budget and
privacy; only its private generation ID changes. Total backend attempts remain
at most two. Cloud privacy and the additional-request budget (default zero)
are checked before notification or waiting.

Retry-After accepts delta seconds and HTTP dates; a supplied clock makes dates
testable. Missing/invalid values use the existing bounded backoff. Values above
the configured cap preserve the original HTTPStatusError without retry. For
api.groq.com only, zero daily remaining requests also refuses the retry.
There is no quota polling, model substitution, network capability discovery,
tool dispatch/replay or shared mutable request budget.

No nonempty text, tool_request, finished or buffered-tool intent may have been
emitted in the failed generation. Cancellation interrupts both the notification
callback and subsequent wait; owned callback/wait tasks are joined. The callback
is invoked once only for an accepted 429 wait and receives the original request
and safe delay, never the response body/headers.

The protocol references were checked against
[HTTP Retry-After](https://httpwg.org/specs/rfc9110.html#field.retry-after) and
[Groq rate-limit headers](https://console.groq.com/docs/rate-limits).
Groq documents remaining-requests as requests per day; this meaning is not
assumed for other providers.

## Verification

- New policy assertions against the unchanged HEAD failover source injected
  only into an isolated pytest process: **29 failed**, exit 1. This is an API
  and policy baseline, not a claim that all 29 are separate production incidents.
  See `before-tests.log` and `before-failover.py`.
- New policy plus original failover contracts and actual main/Core/SQLite retry
  integration: **63 passed, 3 dependency warnings, 4.50s**. See `tests.log`.
- Ruff check: PASS (`ruff.log`). Format: PASS (`format.log`). Mypy: PASS, two
  files (`mypy.log`). Scoped diff whitespace check: PASS.
- The new true loopback HTTP test uses the production OpenAI-compatible HTTP
  transport: 429/Retry-After 0.015 followed by SSE 200; exactly two byte-identical
  wire payloads, measured second arrival >= 0.015s, and successful completion.
- Cases cover date/past-date/injected-clock handling, invalid and missing headers,
  finite cap, daily exhaustion, explicit cloud budget/privacy, two-attempt cap,
  no provider substitution, all emission fences, token/task cancellation,
  cancellation during notification and unchanged default behavior.

Commands:

```text
.venv/bin/pytest -q tests/contract/test_rate_limit_recovery.py tests/contract/test_failover_policy.py tests/integration/test_provider_retry.py
.venv/bin/ruff check src/siro/adapters/models/failover.py tests/contract/test_rate_limit_recovery.py
.venv/bin/ruff format --check src/siro/adapters/models/failover.py tests/contract/test_rate_limit_recovery.py
.venv/bin/mypy src/siro/adapters/models/failover.py tests/contract/test_rate_limit_recovery.py
```

## Limits and rollback

This does not add API quota. A repeated 429, daily exhaustion or wait above 60s
still fails visibly through the existing error path. True Groq, actual owner GUI,
speech, release CI and deployment acceptance are NOT VERIFIED by this subtask.
All requests are synthetic and use temporary test DBs or owned loopback servers;
no private DB, model weights, credentials or running port-8000 service was used.

Omit `rate_limit_max_wait_seconds` to restore the original wrapper policy. Keep
the default additional-cloud-request budget zero unless explicitly authorized.
No DB/config/state rollback or side-effect replay is required.
