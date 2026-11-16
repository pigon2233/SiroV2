# P0-6 halve time-to-first-token

- Task: P0-6 — timing instrumentation, system-prompt dedup + stable prefix, snapshot tests, TTFT bench.
- Owner/session: Claude (Opus 5.5) Claude Code session, 2026-11-16 (Asia/Taipei).
- Status: IN_PROGRESS
- Base SHA: d12708d68300b2aaff80bbc0076b2fd437d6e623 (origin/main)
- Branch / worktree: `perf/p0-6-ttft` / `SiroV2-wt-p06`
- Remote: the owner explicitly authorised `git push -u origin perf/p0-6-ttft` for this task only.
  No merge, no PR, no change to main.

## Owned paths

- `src/siro/core/memory.py` (`assemble_prompt` only)
- `src/siro/core/conversation.py` (timing log)
- `src/siro/core/companion.py` (prompt-assembly timing)
- `src/siro/services/tools/orchestrator.py` (`ToolCatalogSnapshot.model_context` only)
- `src/siro/services/presentation/integrated.py` (capability block placement, turn timing)
- `src/siro/services/presentation/gateway.py` (STT timing log only)
- `src/siro/services/audio/stt.py`, `src/siro/services/audio/local_stt.py` (timing log)
- `src/siro/adapters/models/ollama.py` (done-event timing log, keep_alive hook comment)
- `scripts/bench_ttft.py`, `tests/unit/test_prompt_prefix.py` (new)

## Excluded

`src/siro/services/computer_use/`, `src/siro/core/computer.py`, `desktop-win/computer-*`,
`desktop-win/input-helper.ps1`; keep_alive policy (P0-5); shared STATUS/TASKS files.

## Acceptance

Stable prefix byte-identical across turns with different time/memory/state; capability
dedup within a char budget; ruff + relevant pytest pass; TTFT numbers only if Ollama is reachable.
