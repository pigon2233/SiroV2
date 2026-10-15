# D57 — owner task API and independent caller review

Final verification date: 2026-10-15. Work began 2026-10-14. This subtask added only `tests/integration/test_goal_task_api.py` and API evidence. Production fixes were performed by the root agent; this reviewer did not edit production or old tests during the API subtask. The separately completed Rust leaf stayed frozen.

## Final result

Actual Python 3.14.4: **66 PASS / 0 FAIL / 3 existing warnings / 4.74 seconds** (5.902 seconds including process startup). Mypy, Ruff lint and Ruff format check all returned EXIT 0. The eight bound source/test hashes were equal before and after the final run. The final test file is frozen at `dcbce0837cf903d211d40a3701ed1b75cb7232290ab8d3d5346d32858e609f0b`; see `final-result.json` and `final-api-tests.log`.

Final Gateway: `9e52cd7c7e4ec392d80901619310eedeaa76d2ad1d82701602f6eed55c4f812b`.

Final task owner: `0b0ecfc2099e1538068e15925b5eaad1ce0b0c05a91046b5849687876779bc3a`.

Frozen Rust leaf: `336d34244c4adf3f2252dc7283f9540018de689a10de3f0b38220da878609520`.

## Actual coverage

- Every task route requires Bearer authorization. Mutations require the allowed owner Origin. Closed paths bodies and strict positive integer revisions reject extra fields, type coercion and oversized collections. Auth, wrong method/action, validation, unavailable and unexpected producer errors all retain `Cache-Control: no-store`.
- Missing, legacy or unstarted owners return safe unavailable responses. GET does not initialize, migrate, or read the unstarted store. Unexpected producer error strings, workspace roots and synthetic key canaries do not enter responses.
- Full authorization mode still leaves new tasks PROPOSED with no reads until an explicit matching-revision approval. Source results contain actual SHA256, line numbers and observation time; unmatched synthetic private text and the absolute workspace remain absent. Reading TODO lines does not execute those TODOs.
- Wrong-session controls and deletion are rejected. A different session cannot read the active goal identity. Pause/cancel can stop progressed work using a stale displayed revision; approval/resume/deletion retain their stricter revision checks.
- Controlled reads that suppress the first cancellation must finish/join before pause, cancellation, tools-off or foreground responses return. Late read results cannot produce completed observations after fencing. Shutdown closes the task owner before the workspace callback and persists its pause reason.
- Actual main composition holds its data owner, initializes SQLite, constructs the real task owner, starts the actual Rust workspace and accepts the HTTP task flow through TestClient's ASGI transport. Real Rust results match fixture source bytes. Candidate feature-off and legacy profiles preserve the existing snapshot and reject the new API. These tests do not launch a TCP server or replace the user's live service.
- The synthetic schema13 fixture migrates additively to14 while retaining the old goal fields, null task metadata, and all thirteen applied migration/checksum rows. A complete independently framed and signed v2 source approval restricted to schema13 resolves before migration and is refused against14 by both schema13 and schema14 launch managers. Refusal preserves the post-migration SQL dump and active pointer. No source is imported/executed or automatically re-approved in this fixture.

## Findings and local corrections

| Confirmed issue | Evidence | Correction and final gate |
|---|---|---|
| Active goal UUID crossed the session-filtered snapshot | Source review found global `_active` returned alongside owner-filtered goals. This was already corrected before the first API run; no pre-fix runtime RED is claimed. | Project the active ID only when present in the owner's filtered goals. Final cross-session HTTP case passes. |
| Valid filename `none` collided with the planner's do-nothing ID | `planner-collision-red.*`: **1 FAIL / 4.01s**, task paused as foreground with zero reads; owner source hash `93ad626a...`. | Prefix only the trusted read candidate ID; path and planner scoring remain unchanged. The final filename case completes with one verified observation. |
| Foreground hydration window admitted a background read | `foreground-window-red.*`: **1 FAIL / 1.16s**. Actual main's session-history await was held while Gateway showed responding and Integrated had not yet set its active-session flag. The task incorrectly completed a real Rust read. | Main's existing busy predicate also covers Gateway responding/awaiting-approval states. Final controlled case pauses before spending/reading. |
| Callback errors made the added busy gate persist after failure | `callback-shortcut-red.*`: first of **2 FAIL / 4.22s**. Actual main returned HTTP500 but retained responding; the next approved task stayed paused indefinitely. | Mark only the matching turn failed and rethrow the original error. Final actual-main failure case permits the next approved task. |
| Opted-in shortcut returned before pausing/joining an active read | `callback-shortcut-red.*`: second of **2 FAIL / 4.22s**. A supported candidate app with explicit legacy-shortcut opt-in returned awaiting-approval with its prior read still active. No shortcut executor ran. | Move the existing foreground hooks before the early return. Final HTTP shortcut case joins and preserves unknown intent without a late observation. |
| Older turn completion/error could overwrite newer same-session state | Necessary identity review following the callback correction; no pre-fix runtime RED is claimed. | Both completion and failure writes use the existing turn ID. Two final controlled HTTP cases retain the newer responding state until its own callback completes. |

The root also contained invalid optional task metadata at startup so the optional caller can remain unavailable without breaking existing chat. This document does not claim an independent corrupt-startup test; that gate belongs to the service/full suite.

## Intermediate runs and remaining scope

The initial 60 API cases passed before the additional controlled counterexamples. The candidate62 run passed after the planner/window fixes; **80 existing release-selection, signed-launcher and actual source-process cases also passed in 7.61 seconds at that candidate**. That earlier receipt is preserved in `candidate-62-final-result.json` and `schema-release-gate.log`; it is not represented as final-source release acceptance after later callback/shortcut amendments. The final whole-tree check is owned by the root agent.

The first66 functional run passed but failed Ruff SIM117 in the newly added test. It is preserved as `pre-format-*` and is not whole-check PASS. Only that test's nested context was combined; the final66 run, type, lint, format and source hashes all passed afterward.

One ephemeral synthetic test token in the planner RED assertion representation was redacted; the result, source hash and failed assertion remain unchanged. The test fixture now excludes authorization headers from its repr.

No original test file was modified. No live8026, private DB/chat/audio/key/config/model, GPU, real provider, real device, publishing or deployment was accessed. This verifies a fixed approved read-only task caller and cancellation/status contracts; it does not establish autonomous goal invention, executing TODOs, model/voice quality, arbitrary code safety, universal filesystem IO cancellation or long-running autonomy. Rust parent-alias/path-race and regular-file latency limits remain as stated in the Rust leaf report. Release approval for a14-schema runtime and safe operational rollback remain separate gates; old13 approval is not silently widened.

No remaining actionable blocker was found in this bounded API/service review. Broader final-source regression and actual page/runtime acceptance must retain their own receipts.
