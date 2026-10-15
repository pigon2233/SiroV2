# D57 frontend acceptance — 2026-10-14

## Scope

Only production change: `src/siro/services/presentation/static/index.html`. Only new test: `tests/integration/test_frontend_goal_tasks.py`. No original test changes, new dependency, live browser/service use, private data access or commit. Main composition, HTTP, Rust and durable owner verification belong to the parent acceptance, not these Node scenarios.

## Behavior verified

The actual page offers an explicit selected-file proposal, exact displayed revision/path review and separate approval, including full mode. It shows source hash, line, time, approval time, known observation / unknown intent / unread differences. Reading does not claim that TODOs were performed. Terminal controls only clear history.

Mutation submission is exactly one fetch, including authentication rejection; unknown submission requires successful manual GET readback before any next mutation. All requests have an owned five-second timeout and abort / generation / control-owner / session guards. Refresh, foreground, tools-off, reconnect, disconnect and unload retire stale output. Polling sends GET only, stops for terminal / dormant tasks and is limited to thirty polls before manual refresh. File content uses plain text; closed response shapes reject leaked or authorizing fields, malformed scope and provenance.

Legal saved paths with internal / boundary spaces and `.git` components display exactly as returned by the server. The create form declines boundary spaces without normalizing selected paths; internal spaces and Unicode are valid. C0/C1 controls match the Core rejection rule. User wording says “首尾空白”.

## Evidence

- Baseline commit: `5c67c6f78f36833e526626b2d3481654bd823165`.
- Final tests against the original page in an owned temporary fixture: **72 FAIL / 3.12s**, exit 1. Fixture removed. See `baseline-red.log`.
- C1 guard before the local repair: **1 FAIL / 12 PASS / 59 deselected**, exit 1. See `c1-red.log`.
- Final actual page plus all original frontend and inventory scenarios: **320 PASS / 19.45s**, exit 0; **72 new + 248 original cases**. See `final-green.log`.
- Ruff format/check, mypy for the new test and scoped diff whitespace check: **PASS**, exact commands / exit codes in `static-checks.log`.
- All 11 original frontend/inventory test files retain exact baseline bytes. Final source/test and original test SHA256 identities are in `RESULTS.json`.

An initial generated Node fixture had a linebreak syntax error; it was corrected before the complete final baseline proof. That initial result is not counted as evidence of a product defect. Earlier `/tmp` logs remain for traceability.

## Limits

These are deterministic actual-page Node DOM, fetch and socket scenarios with a manually advanced clock. They do not demonstrate a real browser layout, production deployment, real model reasoning, private conversation use, hardware safety or long-term autonomy. No runtime task invents goals or gains authority through file contents.
