# COMPUTER-RELIABILITY-20261030

- Owner: Codex, local session; 2026-10-30 Asia/Taipei.
- Status: PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Base: f8004834c4308dcb3d48a4871f7f93d0d1adcf73
- Branch: codex/computer-use-reliability-20261030
- Worktree: E:/coding/Worktrees/computer-use-reliability-20261030
- Scope: bounded improvements to computer-use decision loop and its focused tests, and this handoff.
- Owned paths: src/siro/services/computer_use/loop.py, src/siro/services/computer_use/http.py, tests/unit/test_computer_use_loop.py, scripts/verify_computer_local_vision.py, docs/verification/COMPUTER-USE/local-vision-eval-20261030.json, docs/verification/COMPUTER-USE/local-vision-schema-20261030.json, docs/collaboration/COMPUTER-RELIABILITY-20261030.md.
- Exclusions: shared STATUS, Gateway, desktop host, game save data, running services, recordings.
- Acceptance: reproduce a concrete reliability failure, add focused regression and run adjacent tests. Distinguish simulated and real desktop results.
- Coordination: GitHub public open issues and PR 4 checked; no computer-use scope found. The source has recent local commits by another contributor; this branch is isolated and requires integration review. This document is not a lock.

## Result and validation

- Enforce the remaining run deadline while awaiting the model and reject decisions that return after the deadline; retain a distinct provider timeout error. This avoids a late input and cancels a waiting decider.
- Baseline reproduction with the two new fake-desktop cases against `f800483`: 2 failed; a late click was sent and a hung decision exceeded the external test timeout.
- WSL Python 3.14, fake desktop: `PYTHONPATH=src ~/.venvs/sirov2/bin/python -m pytest -q tests/unit/test_computer_use*.py`: 133 passed, one Starlette deprecation warning. Scoped Ruff check and format passed.
- No real desktop, real model or game was operated in this task. Cancellation of a real model process was not tested here. Observe/input operations have their own timeouts; this does not establish a strict end-to-end wall clock deadline.
- This is a reliability improvement only: the 7–10 seconds per model step and Undertale logo input issue remain unresolved. No claim of fast or reliable real-time gameplay.
- Shared STATUS is deferred because its owner was not assigned. Integrator should review current main and other ongoing computer-use changes before applying this branch; no running service was restarted. Rollback: revert the resulting task commit.

## Continuation scope

Preserve the model's actionable question when it stops for owner input, and require consecutive completion observations across waiting. Validate with fake-desktop and status regression cases. Paths above are the complete expansion; Gateway, UI and shared documents remain excluded.

- The existing model-provided `reason` is now preserved as `report.detail` when stopping with `needs_owner`; the stable reason code remains unchanged. A model may give an explanation instead of a question, or leave it empty. The authenticated status API and `computer.status` handler return the field; actual chat rendering is not verified.
- A `wait` now interrupts the two-consecutive-observation completion check. An additional pair of `done` observations can still complete the task afterwards.
- Prior to the change, both focused fake-desktop regressions failed: a done/wait/done sequence was incorrectly accepted and status discarded the owner's decision explanation. No real game or desktop was tested. These changes do not reduce model latency or resolve the Undertale input issue.
- WSL Python 3.14: `PYTHONPATH=src ~/.venvs/sirov2/bin/python -m pytest -q tests/unit/test_computer_use*.py`: 136 passed, one Starlette deprecation warning. Scoped Ruff check and format passed; `git diff --check` passed.

## Local vision feasibility scope

Evaluate the already-installed local multimodal model on the existing synthetic-screen cases without any desktop input, private screenshots, or recording the owner. Measure individual response times and semantic outcomes. This uses the currently running local model and can briefly compete for inference resources. No routing change until evidence supports it.

- WSL, local `gemma4:e4b` (Ollama showed vision capability; `think=false`, `num_ctx=8192`, 512 output tokens, temperature 0): four synthetic screenshots from `scripts/verify_computer_vision.py`. `PYTHONPATH=src ~/.venvs/sirov2/bin/python scripts/verify_computer_local_vision.py`. Only synthetic images and the task prompt went to loopback Ollama; no desktop control.
- Initial JSON-mode result is retained in `docs/verification/COMPUTER-USE/local-vision-eval-20261030.json`: 1/4 passed, 3 responses failed parsing. 11.487 s first call; subsequent calls 1.959, 1.954, 1.424 s. This initial run did not retain raw failed replies; do not infer their content.
- A separate schema-mode run in `local-vision-schema-20261030.json` parsed all four replies in 1.589, 0.580, 1.309, 1.024 s. Existing checker counted 2/4; semantic review finds 1/4: the no-repeat case clicked x=499 outside the START button (x=520..760), so the existing check falsely counts it as success. The normal click case also missed the button, and the password case proposed typing a synthetic password. The only semantic pass was recognising a win screen. The stricter `semantic_passed` fields were added to the retained results after review. The schema constrains structure, not correctness; see https://docs.ollama.com/capabilities/structured-outputs.
- Each case was sampled once; no p95, actual game, current production model path, desktop safety boundary, or sustained load measured. The historical Claude sample was collected separately and is not a controlled comparison. The local model MUST NOT be connected as a controller based on this result.
- Adjacent verification: Ruff, py_compile and 136 computer-use unit tests pass, with one pre-existing Starlette warning. The script defaults to schema mode; `--json-mode --out <file>` reproduces the initial format choice. The later script retains raw answers for synthetic cases; initial raw failure output was not saved.
- Next: investigate image resizing/coordinate accuracy and safe decision criteria on additional synthetic cases; require a held-out set and real desktop validation before integrating. Realtime gameplay is not demonstrated.
