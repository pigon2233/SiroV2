# CLAUDE-BUDGET-SHARED-20261116

- Task: one process-wide rolling Claude CLI budget and rate-limit cooldown for every non-computer-use caller
- Owner: Cursor cloud agent (this session)
- When: 2026-11-16 UTC
- Status: IMPLEMENTED, not merged. Computer-use patch is not applied.
- Follow-up: fast-forwarded `bac26f2` (WIP review fixes) and finished the lock, patch, and timeout note on this branch. Do not rebase onto main until PR #16 is accounted for. At that rebase, the profile line in `gateway.py` should become `cast(Completer, ClaudePlannerModel(claude_model(), caller="profile"))`.
- Base SHA: `d12708d68300b2aaff80bbc0076b2fd437d6e623` (origin/main). The read-only audit was of `335aaa6`; the only commits after it add the owner VRM asset and do not touch Claude call sites.
- Branch: `cursor/claude-shared-budget-bbf9`
- Worktree: `/agent/repos/SiroV2`
- User authorization: the task asks for a new branch and a PR against main, and explicitly says not to merge. Push and PR creation are in scope for this task only.

## Owned paths

- `src/siro/adapters/models/claude_budget.py`
- `src/siro/adapters/models/router.py`
- `src/siro/services/tools/claude.py`
- `src/siro/services/presentation/gateway.py`
- `src/siro/services/agent/planning_adapters.py`
- `src/siro/services/agent/addressee.py`
- `src/siro/services/agent/auto_plan.py`
- `src/siro/services/agent/self_activity.py` (comment only)
- `tests/unit/test_claude_budget_guard.py`
- `docs/patches/claude-budget-computer-use.patch`
- `docs/MODEL_ROUTING.md`
- `docs/CONTRACTS.md`
- `docs/DECISIONS.md`
- `docs/collaboration/CLAUDE-BUDGET-SHARED-20261116.md`

## Excluded

- `src/siro/services/computer_use/**` (user edits these; suggestion patch only)
- `src/siro/core/computer.py`
- `desktop-win/computer-*`, `desktop-win/input-helper.ps1`
- `docs/STATUS.md` — open PR #13 lists it as an owned path. This task records the handoff here instead of writing that file.

## Remote check

Open PR #13 is the desktop pet GPU change. It does not touch the Claude budget paths. No open issue claims this budget work.

## Verification (this environment, 2026-11-16)

- `git apply --check docs/patches/claude-budget-computer-use.patch` succeeded. `git diff` for `src/siro/services/computer_use`, `src/siro/core/computer.py`, and `desktop-win` is empty.
- `PYTHONPATH=src uv run pytest tests/unit/test_claude_budget_guard.py tests/unit/test_model_router.py tests/integration/test_claude_tool.py tests/unit/test_computer_use_router.py tests/unit/test_computer_use_playbook.py tests/unit/test_addressee.py tests/unit/test_auto_plan.py` — 58 passed.
- `PYTHONPATH=src:. uv run pytest -q --tb=line` — 3442 passed, 83 failed, 127 skipped. Failures are the environment's missing Rust runtime, missing `tokenizer.json`, missing `claude` binary, and the existing `screen.png` expectation against `screen.jpg` in computer-use. None of the failure lines mention the new budget module. `docs/STATUS.md` was not edited because open PR #13 owns it.
- `uv run ruff check` on the touched Python files passed. `uv run mypy` on the budget module, router, claude tool, planner, addressee, auto-plan, and the new test passed. Full-repo mypy and a live Claude CLI were not run.

## Acceptance

- Existing router budget tests still pass.
- New unit tests: shared counter, over-budget fallback, shared cooldown, `SIRO_CLAUDE_TIMEOUT_SECONDS`.
- Patch file is not applied.
