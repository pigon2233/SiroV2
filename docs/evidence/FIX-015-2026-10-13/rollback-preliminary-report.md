# FIX-015 source-only rollback verification — 2026-10-13

Status: **PRELIMINARY_REHEARSAL_PASS_AWAITING_ROOT_FREEZE**. Only SQLiteStore, CLI and two new test files are in the exact patch. A disposable code-only copy successfully passed reverse check, reverse, reapply check and reapply; its bytes matched the captured prior dirty baseline / current source exactly. New tests disappear on reverse and return exactly on reapply.

All269 other baseline files stayed unchanged before and after. All271 baseline hashes and the4 current scope hashes were rechecked after the rehearsal; the temporary copy was removed. No main-workspace source rollback, Git index/authhelper changes, private blob/runtime/data access occurred.

This restores source bytes only; it does not restore, rewind, repair, or recover any database, backup, conversation, audio or other user data. Undoing the fix reintroduces the confirmed backup cancellation/temporary cleanup defect and must not lift its release blocker.

Exact scopes/digests/commands are in rollback-preliminary.json; repair patch SHA is bound there. Root freeze has not been announced; this is preliminary, not final acceptance.
