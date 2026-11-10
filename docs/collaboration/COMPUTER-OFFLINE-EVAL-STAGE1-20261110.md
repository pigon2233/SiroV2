# COMPUTER-OFFLINE-EVAL-STAGE1-20261110

- Owner: Grok Bot; 2026-11-10 Asia/Taipei. LOCAL_ONLY / NOT PUSHED.
- Scope: only owner-requested improvement Stage 1 (not the old implementation-plan Stage 1).
- Base: `00a8bd768c596df0a9a7d14dde61d378eccfba68`; branch/worktree: existing local `main`, `E:/coding/股票策略機器學習/SiroV2` as explicitly requested.
- Initial worktree: clean. Owned: new `scripts/computer_click_eval.py`, `tests/unit/test_computer_click_eval.py`, `docs/verification/COMPUTER-USE/stage1/`, this handoff; local ignored `.siro-data/computer-bench-stage1/` only.
- Excluded: runtime modules, safety gate, allowlist, hotkey, model prompts, OCR, action batching, refactor, foreground-name matching, running services, secrets/config files, shared STATUS/DECISIONS.
- Coordination deviation: user explicitly requested this checkout/main; no branch switch, remote claim, push or PR. No remote coordination claim asserted. No overlapping dirty work present before edits. Existing computer tasks concern runtime modules, which are untouched.
- Read: AGENTS, AI_COLLABORATION, STATUS, SOL_RUNBOOK, both computer plans, loop.py, decision.py, perception/demos/framedump and existing bench/tests.
- Capture review: selected three unique already-saved raw STS2 frames from `siro-computer`; manually reviewed visible targets. No historical action is asserted successful. Duplicate learning images, desktop, numbered grounding/map/atlas images excluded to avoid Stage 2 contamination.
- Acceptance: immutable SHA256/size-checked manifests; strict click hit testing; mean/median request wall-clock seconds; per-provider unavailable/error reporting; never instantiate bridge/loop or send input. WSL only, `UV_PROJECT_ENVIRONMENT=~/.venvs/sirov2`; Ollama benchmark context 8192.
- Status: PARTIAL (tool and fixed mini-set complete; local/Groq measurements blocked). No Stage 2 work.

## Results / handoff

- Added only seven task-scoped text files: evaluator, unit tests, stage1 README/cases/baseline/tests JSON, and this handoff. Existing tracked files unchanged. Three private frozen game images live in ignored `.siro-data/computer-bench-stage1/frames/`; no screenshot committed.
- Real baseline `2026-11-10 20:16 Asia/Taipei`: Claude 3/3, mean 6.026232849 s, median 5.872511252 s. Gemma4:e4b 3/3 requests timed out at 90 s, no valid decisions; Groq key absent in evaluator environment, not measured. Do not interpret unavailable backends as zero accuracy.
- Ollama read-only diagnostics: context 8192, GPU 7744/8192 MiB and 100% utilization during timeouts. No service/config/workload changes; no unbounded retry.
- Verification: new tests 28 PASS; full computer-related Python suite 238 PASS / 4 FAIL (33.39 s). Existing perception file independently 27 PASS / same 4 FAIL (3.13 s), without the new test module. Four existing expectations/errors recorded in stage1/tests.json; not repaired out of scope. Ruff check/format and mypy on both new files PASS; manifest hashes/dimensions/boxes PASS.
- Measurement uses shared production `_decide_once`, one request per case without hidden retries; prompt/grid/request/parse wall time only, not full loop latency. Claude-only opt-in allowed reviewed game crops; no real input.
- Deliberate non-changes: runtime decision.py/loop.py, safety, allowlist, emergency stop, OCR, batching, split/refactor and title matching. Shared STATUS/DECISIONS left to their owner per ownership rule; this handoff carries status instead.
- Local delivery follows AGENTS mandatory local-commit convention; no push/PR. Final commit SHA is available from `git log -1` for this task (not embedded self-referentially).
- Next: stop here. Owner may separately resolve Ollama resource/timeouts and supply Groq via its normal environment before rerunning the exact dataset. Only start Stage 2 after owner says continue. Do not use three easy UI targets as evidence of general game strategy ability.
- Rollback scope: only the seven added task files and ignored task-specific snapshots; no runtime behavior to revert. Do not delete other data or restore unrelated paths.
