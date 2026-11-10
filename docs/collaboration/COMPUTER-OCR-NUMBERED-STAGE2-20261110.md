# COMPUTER-OCR-NUMBERED-STAGE2-20261110

Owner: Grok Bot. Offline implementation/comparison completed, 2026-11-10 Asia/Taipei.
Status: PARTIAL verification / LOCAL_ONLY / NOT PUSHED. STOP at Stage 2; do not begin Stage 3.
Base: 87a23b42ef762532d999f5ff7bd0ab2d78b50621.
Branch/worktree: existing local main, E:\coding\股票策略機器學習\SiroV2. Owner explicitly requested this checkout, overriding isolated-worktree default; clean at start. No remote claim/assertion. Commit full SHA is supplied in final delivery after creation; resolve this task's complete SHA with git log -1 --format=%H -- docs/collaboration/COMPUTER-OCR-NUMBERED-STAGE2-20261110.md.

## Scope and ownership

Owned paths: scripts/computer_click_eval.py; scripts/windows_ocr_blocks.ps1; src/siro/services/computer_use/{ocr.py,numbered.py}; only make_decider wiring in decision.py; tests/unit/test_computer_use_numbered.py; docs/verification/COMPUTER-USE/stage2/**; this handoff.
Excluded: loop/safety/perception/allowlist/emergency-hotkey behavior, shared STATUS/DECISIONS, Stage 3+, deployment, service/config changes, push/PR. No unrelated dirty changes observed.

## Delivered

- 20 manual, explicit-control tasks on 5 unique saved STS2 frames (15 text, 5 no-text icons); source/transform/hash/uncertainty recorded. No historical-success or best-gameplay claims. Related traces/worktrees/Pictures inspected; no usable saved 2048/Notepad frame found. Correlated development set, not independent held-out scenes.
- New Windows.Media.Ocr helper operates ONLY on supplied image bands. OCR pipeline=3: generic grayscale/upscale bands, correct TextAngle rotation back to original coordinates, stable block IDs and validated image-SHA caches. Five frozen text-only caches and inventory hashes committed; source screenshots remain ignored under .siro-data/computer-bench-stage2/frames.
- SIRO_COMPUTER_OCR_NUMBERED defaults off. Model returns only integer ID; code computes block center. No pixel fallback or input execution. Cloud consent required. No semantic confidence invented: confidence=0 preserves existing non-autonomous stop; original verifier remains downstream. Runtime model-only/frame replay metrics are NOT end-to-end loop claims.
- Offline tool has pixel/numbered modes, freeze-OCR option, no-text strata and target-center coverage. All Ollama calls context=8192. All real comparisons completed and saved before continuation; no duplicate remeasurement after the 22:00 Asia/Taipei resume request.

## Measurements

Same manifest SHA256 914077f0196b22cb93dc08413668656f478e7066c097a683c740ec46c350a00a; 20 cases each:
Claude pixel: 20/20, mean 6.000788 s, median 5.511976 s.
Claude numbered: 11/20, mean 4.212181 s, median 4.143234 s.
Gemma4:e4b pixel GPU24: 0/20, mean 15.876620 s, median 15.191521 s; 8 parse errors counted as misses.
Gemma4:e4b numbered GPU24: 12/20, mean 1.290889 s, median 1.370763 s; no parse errors.
Both numbered modes: no-text 0/5; text-only Claude 11/15, Gemma 12/15. OCR center coverage 13/20; Defend/event Continue lacked usable text boxes; garbled combat End Turn led both models to abstain. Claude additionally selected one wrong block.
Groq both modes not measured: no key in calling WSL environment; no credential-file extraction or questions.
Numbered latency includes frozen-cache lookup, NOT fresh OCR. Unique-five cache-miss OCR mean 0.896242 s, median 0.589426 s; Windows was already warm from development. See comparison.json, README.md and source reports for exact values/limits.

## Ollama investigation

User-level Ollama 0.34.3 log showed fatal draft-model vector range load failure/HTTP500, not just conjectured GPU pressure. Supported request-only draft_num_predict=0 loaded successfully. Automatic GPU numbered trial later saturated GPU (7897/8192 MiB, 100%) and discovery watchdog used stale memory estimates; this is a correlated observation, not proof of a sole cause.
Stopped ONLY own stuck evaluation. No service restart, other-workload termination or persistent configuration change. One GPU24 probe succeeded; matched pixel and numbered GPU24 comparisons then completed with bounded 120s calls. Both modes share resource flags; one warm-up probe excluded. Benchmark resource options are separately opt-in/default-unset. Initial/preflight/interrupted diagnostic evidence retained; repaired PowerShell's accidentally oversized diagnostic-object serialization into the original 23 plain log lines.

## Verification

All in WSL, UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2, uv run --no-sync; no Windows uv run.
52 new tests + 28 existing evaluator contracts = 80 passed.
Full computer unit/integration regression: 290 passed / 4 existing failures, same perception fixtures as Stage1: screen.png path; transient claude_failed; missing_expect; saw: vs saw= history. Not relaxed/deleted or declared passing.
Ruff/check-format/mypy (four owned Python files) and frozen manifest validation pass. tests.json contains complete commands/results.
Final fixes after reading errors: valid fixture clock, lowercase production timeout code in fail-fast, correct use of uncertainty vs confidence. Only metadata/error handling changed after measurements; prompts/click coordinates/labels unchanged.
Mock loop test verifies confidence=0 stops at original low_confidence gate before act; offline tests fail on capture/input attempts. No hardware input/live game verification, packaged-wheel verification or full-project test claim.

## Handoff / rollback

Keep experimental mode default off: Claude's overall accuracy regressed; local text selection improved but icons/cards/OCR gaps remain. Do not start Stage 3 without owner's next instruction. Reproduce with README commands and frozen caches; all source image hashes must match. No measurements/jobs remain running; existing companion/gateway services were not ours and remain untouched.
Shared STATUS/DECISIONS deferred because not owned. Full final SHA and clean/dirty status supplied with delivery. Local-only rollback can leave feature flag unset; any revert must preserve later/unrelated changes. No reset/clean/force, no push.
Local-only inspection contact sheet C:\Users\pepepig\siro-computer\stage2-inventory.jpg was not committed or sent to a model; source frames/caches under .siro-data are ignored.