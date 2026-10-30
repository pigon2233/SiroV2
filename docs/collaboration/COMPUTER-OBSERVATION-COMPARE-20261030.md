# COMPUTER-OBSERVATION-COMPARE-20261030

- Owner: Codex; branch `codex/computer-observation-compare-20261030`; base `608a4865a2d18d7ec21e199fb1e0703747350d7d`.
- Scope: correct post-action screen-change comparisons when fingerprints or window identity are unavailable or change; retain unknown rather than inventing a result. Tests and this handoff only. No real inputs or service changes.
- Allowed paths: `src/siro/services/computer_use/loop.py`, `tests/unit/test_computer_use_loop.py`, this file.
- Acceptance: regression tests for missing fingerprints, changed windows, and normal same-window comparison; relevant suite passes. PARTIAL / LOCAL_ONLY / NOT PUSHED; independent actual gameplay acceptance remains outstanding.
- GitHub open issues and PR inspected via API 2026-10-30: #1, #2 and #4 concern ESP32. Main checkout has unrelated dirty design files. Local claim is not a lock; check again before changes.

## Results

- A post-action comparison previously treated missing fingerprints as comparable and did not verify target identity. Missing values could appear unchanged or changed; different windows could be compared as if they were the same scene. This is a code-path finding, not a claim that it happened in Undertale.
- Wait and action observations now share the same target/metadata and nonempty fingerprint check. Unknown comparisons remain unknown, do not increment consecutive unchanged actions, and are not recorded as a definite demo outcome. A window title change also yields unknown. Unknown does not prove progress or stop further model decisions.
- Added three simulated end-to-end loop cases for missing before/after fingerprints and window switch. Existing same-window unchanged and changed tests remain in the suite.
- Related WSL pytest suite: 186 passed, one Starlette deprecation warning. Scoped Ruff check and format passed after fixing one line-length error. No real game input, integration, or long-play acceptance was performed. The earlier isolated Electron test shell launch was rejected by automatic review without a specific reason; do not bypass it. Shared status remains for its owner.
