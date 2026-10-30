# COMPUTER-RELIABILITY-20261030

- Owner: Codex, local session; 2026-10-30 Asia/Taipei.
- Status: PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Base: f8004834c4308dcb3d48a4871f7f93d0d1adcf73
- Branch: codex/computer-use-reliability-20261030
- Worktree: E:/coding/Worktrees/computer-use-reliability-20261030
- Scope: bounded improvements to computer-use decision loop and its focused tests, and this handoff.
- Owned paths: src/siro/services/computer_use/loop.py, tests/unit/test_computer_use_loop.py, docs/collaboration/COMPUTER-RELIABILITY-20261030.md.
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
