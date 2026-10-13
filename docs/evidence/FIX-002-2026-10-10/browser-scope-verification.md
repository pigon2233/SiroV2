# FIX-002 — Synthetic Chromium Scope Verification

The final source capture is **CAPTURE_COMPLETE / PASS**. Ten fixtures run through the actual `ScopedBrowserDriver` using two temporary loopback HTTP servers and actual Chromium. Unauthorized origin B received **zero requests**. Browser, server threads, and sockets were all cleaned up. The five production source hashes match at the beginning and end of the capture.

## Verified behavior

| Fixture | Final result |
| --- | --- |
| Allowed A page | Readable A observation |
| Direct B | `BrowserScopeViolation`, `main_origin_denied` |
| Direct B with synthetic userinfo | `BrowserScopeViolation`, `invalid_url` |
| A redirect to B | `BrowserScopeViolation`, `redirect_denied` |
| A with B image, script, or iframe | Readable A observation; actual session serialization reports `partial` / `subresource_denied` |
| A script navigating the main frame to B | `BrowserScopeViolation`, `main_origin_denied` |
| A iframe script navigating the main frame to B | Initial readable A snapshot; subsequent observation rejects the later navigation with `main_origin_denied` |
| A button navigating the main frame to B | `BrowserScopeViolation`, `main_origin_denied` |

The captured request metadata distinguishes ordinary image/script requests, iframe document navigation, and main-frame navigation. No query values, userinfo values, raw exception messages, private data, or external website content are recorded.

## Observation boundary

`DOMContentLoaded` does not mean every iframe or later resource has completed. `partial` means the observation has already seen a blocked resource; it does not promise network-idle or complete resource enumeration. A frame may initiate navigation after an initial valid A snapshot. The probe deliberately allows a bounded 150 ms opportunity for eager child-frame navigation and then reads again. The final driver rejects that later unauthorized main-frame navigation while B remains uncontacted. Arbitrarily delayed or user-triggered future requests are outside this finite capture.

The final source includes the `observe()` error path that consumes a pending denied main-navigation reason when evaluation or title reading fails. These fixtures verify the final version but do not force that timing-sensitive context-destruction exception in every run; a deterministic targeted driver test is needed to establish that specific branch separately.

## Evidence and limits

- `browser-scope-before.json` / `.log`: original source behavior, including image/script causing whole-page rejection and late main-navigation observation gaps.
- `browser-scope-after.json` / `.log`: final source capture.
- `browser-scope-after-before-context-catch.json` / `.log`: previous passing source capture retained before the final context-destruction handling change.
- `browser-scope-after-harness-first.json`: retained first after capture with an explicitly invalid harness expectation; its failed checks are not a production failure.
- `browser_scope_probe.py`: reproducible evidence-only fixture runner.

This is synthetic provider-independent verification through real HTTP and Chromium. It establishes the local scope failure class and repair behavior. It does not establish the exact historical cause of the public Bing report. No production service on port 8026, private database, model, GPU, or voice provider was accessed.

## Final source hashes

- `src/siro/adapters/browser.py`: `da6c4ec180c4134b04b9be601e6562d9ef502e9b30cafb4fe7b0daee99b9371b`
- `src/siro/services/tools/browser_session.py`: `4883c01108751c78d6479b7ad32fa8f350510b7a660325a5868e52c9239de484`
- `src/siro/services/tools/orchestrator.py`: `0eb1d2e7acd596e03bc69cb955ddf46ff2a990815e5b401416fcef2a139d853b`
- `src/siro/services/presentation/integrated.py`: `bef79667f4906695eafe8da54d9308a9a8cf1fca6af50067cfcfdb1dea227e49`
- `src/siro/services/presentation/gateway.py`: `6b7a215439af7dea7641bdebc003ae3568b5b042855a907ce7036982703c1a63`
