# Architecture correction — D48 / FIX-012

## Original decision
T32 ReleaseManager.rollback restores its pre-release whole database backup while selecting last-known-good code. Original integration test requires the later after-release value to disappear. D39 kept this behavior while repairing complete signatures.

## Evidence that invalidates it
src/siro/core/releases.py rollback calls _restore_database before writing active.json. tests/integration/test_release_manager.py expects before-release after a later write. RI-005 explicitly requires later conversation/memory to survive code rollback. Existing separate siro restore already serves intentional data restore.

## Impact
Code rollback can lose every committed write after the backup, including dialogue, canonical memory, completed-effect ledger; restoring a main DB beneath active WAL/writers has additional lifecycle hazards. Not a newly introduced Sol regression.

## Smallest design correction
Separate code pointer rollback from data restore in the same ReleaseManager; persist/verify existing complete manifest for the target and read actual schema metadata before pointer change. No new deployment service, restore framework or schema migration. Unknown/incompatible target refuses without touching latest data.

## Affected RT tasks
T32 historical rollback assertion superseded; RI-005 gets bounded D48/FIX-012 then separate launcher/single-writer integration. FIX-009 signing stays valid. No RT numbering/history rewrite.

## Tasks that remain valid
RI-003 isolated verification; RI-004 fixed approved skills; RI-006 readonly proposals; RT-011/013/015 completed slices. Existing backup/explicit restore remain independent.

## Tasks to cancel / modify
CANCEL automatic whole-DB restore as part of code rollback, including old test expectation. MODIFY RI-005 rollback gate to retained latest data + trusted target/actual schema; KEEP separate deliberate data restore, stopped-writer/launcher/readiness acceptance.

## Compatibility impact
API/CLI/result shape and signature unchanged. Safer intentional semantic correction: rollback no longer removes later data; legacy target without a complete captured sidecar fails closed, never auto-resigns. Data restore uses existing explicit command.

## Migration impact
No SQL/config/package schema migration. New sidecar is local release metadata outside bundle. No DB writes/initialization/migration/replacement by rollback. Same-UID and live schema races remain outside D48; operational stopped-owner gate is not released.
