# D47 Gateway / UI product wiring evidence

Scope: existing presentation gateway and index, plus the two new product test files. `product-frozen.json` captures the exact four final file hashes. Other source edits belong to their assigned owners.

The Gateway injects one candidate-only activation owner into the existing catalog and shared SQLite composition, with the strict worker profile. Prepare only remembers a server-held review. Install, enable and revoke are distinct authenticated, same-origin controls. Input accepts only strict bounded UUID/package identities, never files, source, paths or self-reported PASS. Install/enable reject tools-off; revoke remains available. Lifecycle cleanup closes activation even if candidate cleanup fails, then preserves controller/audio/hub cleanup.

The UI uses separate activation controls. Successful preparation never installs or enables. An explicit install remains disabled; a separate click enables. The usage button fills the existing chat textarea without sending a request. Unknown or malformed outcomes disable further changes and offer an explicit read of current metadata; no activation replay follows refresh/reconnect. All content is rendered as text. Live tools-off events fence late responses and record disabled state; tools-on requires explicit enable.

Two local gaps were reproduced before their repairs:

- `kill-order-before.log`: 1 FAIL / 55 deselected, 0.87 s. Activation was still enabled while Gateway waited for candidate cancellation. Gateway now suspends activation first and always cancels the candidate in `finally`.
- `live-kill-before.log`: 1 FAIL / 24 deselected, 0.22 s. The existing page ignored live kill-switch events. The new activation controls now consume the tools event and fence pending activation responses.

Verification:

- Initial new product/API/UI RED: 79 FAIL, 1.96 s (`product-before.log`). This is an interface/UI RED screen, not an OS security claim. The initial test set was later extended.
- Final new product/API/UI after the history-label repair: **92 PASS, 3.38 s** (`product-new-final.log`): **65 HTTP cases + 27 frontend cases**. `product-collected.log` records the preceding 90-case set, before the two history tests were added. HTTP uses temporary/injected owners; frontend runs the actual page script with synthetic DOM/socket events.
- Owned Ruff check/format: PASS (`product-lint.log`, `product-format.log`). Gateway mypy: PASS (`gateway-mypy.log`).
- Historical combined preserved D44/control run: 172 PASS / 1 FAIL, 7.79 s (`product-complete.log`). Its only failure was the old minimal-review composition fixture, before the separately owned compatibility repair; this log is not final whole-card acceptance.

The card owner's final browser screenshot then revealed a local presentation defect: the upper preparation status still said the skill was uninstalled after the lower activation state confirmed installation. `review-history-before.log` records **2 FAIL / 25 deselected, 0.29 s** before changing index. A readonly label helper now marks an installed matching-hash review as historical after successful actions or accepted metadata. It changes only the status text; exported source/review retains its original unreviewed, installed-false, enabled-false preparation facts. A different installed hash does not relabel the review. `review-history-after.log` records **78 PASS, 3.84 s** across the new 27 frontend cases and 51 preserved candidate/control cases. History-repair lint/format checks passed.

No live 8026 restart, private data read, model request or GPU operation was performed by this work unit. The card owner performs final real-browser/strict-worker acceptance, unchanged composition/full regression and exact source rollback checks separately. No production deployment is claimed here.
