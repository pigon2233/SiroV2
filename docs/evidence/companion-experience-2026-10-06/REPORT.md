# Companion experience repair — 2026-10-07 (Asia/Taipei)

Owner request: make the actual text conversation useful, expose computer assistance beyond the optional workspace, improve the UI, and deliver one genuine Live2D experience with consistent emotion. D32 records the scope. This is a local product repair, not a declaration that all SIRO release gates are complete.

## Behavior and boundaries

- `scripts/start-runtime-product` now loads only allowlisted existing model connection settings, preserves shell overrides, verifies the selected native-budget configuration and local renderer, and fails clearly instead of silently substituting the canned offline model. Injected/test gateway and offline fixtures remain available for their original purposes.
- Real conversation uses the configured provider. Greetings do not require episodic-memory evidence. Runtime facts explain persistent local memory, automatic source recording, bounded completed-dialogue restoration and cloud visibility limits. Local-only source contents remain protected.
- Existing `computer.execute` supports normal account access outside the scoped workspace, through the existing authorization, cancellation and journal paths. Workspace read/list remains an optional restricted interface. Tool proposals keep independent approvals and results. The panel opens on a proposed operation.
- Single Haru character uses verified expression files. Expression application waits for setup completion; reconnect restores only the latest emotion. Old sockets cannot detach their replacement. SDK random expression changes, multi-character switching, duplicate speech synthesis and sample motion audio are disabled. No speech or tool action replays. Local SDK changes are reproducibly applied by the tracked repair script; licensed assets remain untracked.
- UI centers on the character and conversation. Memory and computer assistance are accessible secondary panels; diagnostics are collapsed. Safe DOM formatting handles basic text emphasis and code output without executing HTML. Voice playback is optional.
- Ordered control events own current turn state; a late HTTP response cannot revive a finished turn. Empty provider responses fail explicitly instead of leaving an apparently successful empty reply. Cloud disable blocks new cloud turns and cancels active cloud work.

## Verification evidence

`browser-results-final.json` / `browser-final.log` use the actual configured model, actual local Linux commands and licensed Cubism renderer with isolated synthetic storage. The greeting and memory-capability questions receive natural responses. A two-command task executed `uname -s` and `df -h /` and the model summarized their actual outputs. This validates the ordinary account read path, not arbitrary installation, destructive operations or every application.

Happy F05 survives iframe reload and character tap; sad F08 changes the visible expression. Desktop/mobile screenshots show the actual model; mobile has no horizontal overflow and the recorded browser has no page errors. A repeat patch run performs no rebuild (`renderer-idempotence.log`). Renderer build includes TypeScript validation.

An earlier real tool continuation returned HTTPStatusError after both read-only effects completed. Fresh synthetic continuation and a fresh complete end-to-end run succeeded. Exact cause is UNKNOWN — NEEDS INVESTIGATION; this is not proof of permanently fixed provider reliability. Completed tools were never automatically repeated to recover a failed reply. The first full regression found one obsolete reconnect expectation; it was updated to require latest-emotion restoration without replaying speech/actions. Earlier logs remain historical evidence.

Final automated gate: **460 passed, 5 opt-in skipped, 3 existing dependency warnings**, 105.31 seconds, exit 0 (`regression-final.log`). Whole-repository Ruff check/format PASS (255 files), mypy PASS (195 source files), schema check, shell syntax and diff whitespace PASS. Automated verification uses synthetic providers/temp SQLite. Opt-in provider/speech skips remain skips; separately recorded real conversation probes do not replace all opt-in tests.

Automatic approval review refused diagnostic replay of a saved conversation payload because privacy was not established. That replay was not performed. A newly written, fully synthetic provider case with dummy disk values was approved instead (`provider-synthetic-check.log`). No private dialogue is stored in this evidence folder.

## Deployment and rollback

The 8026 offline demonstration is replaced only after checking the owned PID, command and data directory. The original `.siro-data/siro.db` receives a consistent local backup before startup; no private contents are printed or copied into evidence. Startup uses the existing persistent store and provider settings. No DB schema change is introduced by this experience repair. Product process metadata is in `product-server.json`; operational logs remain local in `.siro-data`. Actual in-app browser reload confirmed the new title, configured cloud route and “Live2D 已就緒 · 情緒與對話同步”; no test chat was submitted against the private persistent store.

Rollback starts with normal drain/stop and retaining the database/journal. Feature flags can disable the earlier runtime slices at the next startup as documented in PRODUCT_QUICKSTART. Do not broadly reset this dirty checkout, delete new memories, or automatically replace the store with its pre-start backup. The local backup is a recovery option, not a claim of deployed rollback testing.

## Limits

One sample Haru is validated; a custom SIRO character and multi-character emotion mappings are not delivered here. Speech/GPU lip synchronization and long-running soak are not verified by this text/renderer pass. Cloud chat does not automatically read local-only saved memories/preferences. Provider reliability, remote CI, distribution licensing and the remaining full-product release gates remain separate work. No new runtime abstraction, provider fallback, permission bypass or RT renumbering was introduced.

The isolated 8027 acceptance service was normally stopped after validation; the user-facing 8026 product service remains running.
