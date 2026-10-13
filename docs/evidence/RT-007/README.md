# RT-007 completion evidence — 2026-10-02

## Selected Task / Why selected
RT-007 工具 catalog 與有效配置。讀取全部 RT status/dependencies（selection.json）；RT-001–006 DONE，RT-007 為最前 PLANNED，RT-003/004 dependencies DONE。只實作本卡，未開始 RT-008。

## Intent and actual runtime path
Objective: descriptor owns schema, handler, readiness; effective runtime configuration is queryable. Existing Gateway main composed handlers separately from Integrated static _AGENT_TOOLS; candidate now assembles ToolCatalog over those same handlers. Integrated → Core.respond tools snapshot → model ToolCall → orchestrator.propose schema/readiness check → approved execute descriptor handler → existing ToolResult observation → Core continuation takes a fresh snapshot. Contextual executor additionally rechecks readiness at scheduled invocation entry. This is connected production composition, not a detached registry.

Authenticated GET /v1/runtime reports the captured actual profile, configuration source, catalog enabled, current routes, authorization mode, switches and redacted tool status. No environment dump or provider secrets. Profile remains captured at startup; env priority stays unchanged. Candidate browser readiness uses the same Chrome/Chromium executable discovery as existing ScopedBrowserDriver.

## Files changed
Production: src/siro/services/tools/orchestrator.py; src/siro/services/presentation/integrated.py; src/siro/services/presentation/gateway.py.
Tests: tests/integration/test_tool_catalog.py.
Documentation: docs/DECISIONS.md (D19 before implementation), docs/CONTRACTS.md, docs/STATUS.md, docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md and this evidence directory.
implementation.patch isolates this task from pre-existing dirty workspace changes; before-digests.json and source-digests.json anchor source versions.

## Implementation summary / Scope discipline
Optional catalog preserves original orchestrator callers. Existing two model schemas move to one shared constant; Integrated retains _AGENT_TOOLS alias for legacy compatibility. Candidate dispatch uses the descriptor executor, not a separate handler map. process.start stays hidden from model schemas and remains a compatibility handler. Invalid arguments/unavailable tools cannot dispatch; stale candidate proposals terminate with existing FAILED semantics. No public enum, persistent format, SiroSettings, Rust protocol, skills installation, model/voice/identity change or architecture redesign.

## Tests run
- Final task-specific: 16 passed (task-final.log).
- Relevant integration/config/cancellation/profile baseline: 73 passed (related.log, before the final scheduled-dispatch test was added; that test is included in final task and full suite).
- Final full suite: 273 passed, 5 skipped, 3 dependency deprecation warnings, 47.39s (full-suite.log).
- Ruff PASS; mypy PASS on 172 source files (ruff.log, mypy.log).
- Real installed siro-gateway startup, authenticated network /v1/runtime and PUT tools-off: PASS (main_smoke.py, main-smoke.log). Smoke sends TERM after checks; process exit -15 proves termination, not graceful active shutdown cleanup.
- Reverse patch applicability: git apply --check --reverse docs/evidence/RT-007/implementation.patch PASS (rollback-check.log); no patch actually applied.

## Regression results
PASS: legacy/candidate startup profile and env priority, default full authorization, existing API/WS/tool behavior, cancellation/session fences, configuration unit tests, existing integrated body/audio fixtures. Full suite includes relevant prior RT regressions.
Five skipped tests are opt-in real external model/speech providers, not silently counted PASS. Real provider/GUI/GPU/long soak and deployment rollback: NOT VERIFIED in this task. Current port 8000 service was not restarted; source completion does not imply that existing process already runs this catalog.

## Acceptance criteria
| Criterion | Verdict | Evidence |
| --- | --- | --- |
| All available model catalog tools routable | PASS | Actual main/Core/SQLite/ASGI production path for both browser.navigate+read and computer.execute, paired tool observations; browser driver and model synthetic, computer real Python subprocess |
| Tools off prevents dispatch | PASS | Revocation between proposal/execution and contextual scheduled invocation, no handler effects; per-round snapshot becomes empty; real network switch makes all catalog entries unavailable |
| No key leakage | PASS | Auth required; strict diagnostic field whitelist; fake secret canary and unused cloud values absent from serialized response; no real secrets read for this evidence |

## Remaining issues / Known limitations
JSON SiroSettings is still not loaded by Gateway main; diagnostic explicitly reports json_settings_applied=false and gateway_env_and_defaults rather than claiming unified config. This existing discrepancy is recorded, no settings redesign. Browser executable readiness does not guarantee display/page availability; handler still owns real permission/target failures. Schema validation implements only the subset used by the current two model tool schemas, not arbitrary plugin JSON Schema. Legacy static behavior and older injected executor fallback remain compatible; catalog_enabled distinguishes that fallback. No global registry, new model-visible tools or dynamic skills installation.

## Architecture deviations
No task scope expansion. JSON/env unification intentionally not performed: task asks for actual effective config and preserved precedence. Additive authenticated diagnostic route documented in CONTRACTS; old routes remain unchanged.

## Rollback method
For future runs choose legacy using existing SIRO_RUNTIME_PROFILE and restart after draining work; never switch a running run's profile. To remove this card's source changes only, verify current digests and reverse implementation.patch (includes the new test), then revert only RT-007 documentation entries. Do not reset the dirty repository or remove prior RT changes. Reverse applicability checked; deployed rollback rehearsal NOT VERIFIED.
