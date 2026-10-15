# D57 actual product loop — completed 2026-10-15 Taipei

**PASS for the approved document-reading slice.** This exercised the actual default candidate launcher/main, real compiled Rust workspace, persistent SQLite goals and actual page through the root agent's In-app Browser. Public copied source, a disposable synthetic account and explicit public renderer were used. No production service, private conversation/data, model, TTS, GPU or hardware operation was performed.

## Actual path

`launch_companion.py → gateway main/controller startup → ReadTaskOwner → existing GoalService / Planner → signed one-use workspace RPC → real target/debug/siro-runtime → SQLite observation → owner UI`.

The fixture imports the existing source-process helper. Its only gateway interposition remaps the account location to a synthetic account and records imported origins; it does not replace main, owner, planner, workspace, HTTP or Rust results. The nonsigned default candidate path is explicit. The actual served page script equals the captured public HTML script, and all source/binary identities are in `RESULTS.json`.

## Three actual process cycles on the same database and random loopback port

| Cycle | Actual owner/UI action and saved result | Real Rust reads |
| --- | --- | --- |
| 1 | IAB selects `notes.md` and creates a proposal. State proposed, revision 1, budget 0/8, no approval or observation. | 0 |
| 2 | Reopened proposal remains unchanged. IAB explicitly approves. Completed revision 7, budget 1/8, SHA256 `66a1a2874d6ca74baeb28060076295517108dcf8454a38e4f54c6bc7d08760e3`, lines 2 and 4, approval/read times. IAB then creates `later.md` and leaves it unapproved. | 1 |
| 3 | Reopened first result keeps its hash/lines/time and used budget. Second proposal keeps revision 1, zero used budget and no approval/observation. There is no automatic reread. | 0 at startup |

The third cycle additionally changes the owned `notes.md` source. Its old completed observation remains historical; an explicit new HTTP proposal/approval reads the corrected source once, with SHA256 `550c0c9ba2f7dd3ced5c7cac2d8e3fd52ff51c2b15b3dfad97ec7ef368c40940` and line 2 `FIXME`. Root IAB manually refreshes and shows old/new provenance separately; the second task remains unapproved.

Other-session history returns an empty list and no active goal. Cross-session approval is rejected with 404 `not_found`; approval with wrong revision 999 is rejected with 409 `conflict`. Both retain the one expected read and add no dispatch. Every task response checked here has `Cache-Control: no-store`.

## Cleanup and binding

All three main children exit on normal TERM with code -15 and actual `Application shutdown complete.` logs. All three real Rust children are gone, each owned runtime socket/ledger directory is removed, the parent probe exits 0 and the complete owned temporary fixture is removed. The copied package, root source and compiled binary hashes remain unchanged. No forced cleanup was needed. Root closes its own IAB tab 6; existing user tabs, including live 8026, are not operated.

`RESULTS.json`, `cycle-1.log` through `cycle-3.log`, the six root IAB screenshots and the reproduction-only `product-probe.py` retain exact evidence. The final reproduction script's own digest is bound in the receipt. Script format/lint pass is in `static-checks.log`.

## Earlier preflight and limits

`preflight/` is a separately cleaned initial UI/proposed probe before the final foreground-gate repair. Its source is superseded and its final acceptance is marked NOT_RUN; it is not mixed into the final three-cycle PASS. Initial subagent CUA had no available browser; root performed the actual IAB actions and retained screenshots.

This validates durable, explicitly approved, bounded readonly execution and useful visible results. Reading completion does not mean TODOs were executed. It does not prove autonomous goal invention, model reasoning quality, learning, long-term/24h autonomy, true voice performance, general computer sandboxing, physical-device safety, signed release handoff or production deployment. Cancellation/interruption/budget/malformed source gates have separate service/API/Rust acceptance and are not inferred from these quick reads.
