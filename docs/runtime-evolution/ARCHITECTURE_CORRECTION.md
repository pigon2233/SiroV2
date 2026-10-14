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


# Architecture correction — D56 / FIX-020

## Original decision
T32 hashes sorted relative filenames and file contents as an unframed concatenation; D39 signs the digest as part of complete manifest-v1, and D52 treats it as source identity for signed launch.

## Evidence that invalidates it
Current `_digest`: `{a:ALPHAb,b:BRAVO}` versus `{a:ALPHA,b:bBRAVO}` have different per-file bytes but identical aggregate digest. True self-owned probe, no candidate code executed, temp removed: [collision-proof](../evidence/FIX-020-2026-10-14/collision-proof.json). This is ORIGINAL_DESIGN_ERROR, not a new implementation regression or SHA256 cryptanalytic collision.

## Impact
An approval of one file tree can authorize another tree with different contents. Immutable capture alone cannot repair the ambiguous approval identity. Release execution remains blocked; no evidence of live exploitation is claimed.

## Smallest design correction
Explicit manifest-v2 selects domain-separated, count/length-framed source-file encoding. Preserve original manifest-v1 payload and hash as inspectable historical data; deny it at execution boundaries. Complete JSON HMAC remains the same canonical mechanism, with the format tag binding the algorithm. No release manager replacement or snapshot/lifecycle implementation in this fix.

## Affected RT tasks
Original T32 identity decision; D39 complete signing depends on corrected source encoding; RI005 D52 exact identity gate FAILED_VERIFICATION/BLOCKED_BY_FIX020. No historical RT renumbering.

## Tasks that remain valid
D39 schema-field signing/canonical JSON, D48 latest-data retention, D49 restore, D50 owner, D51 cleanup, D52 selection/version/readiness with new exact approval, RI003/004, RI006 D55, and RT011/013/015 scopedDONE.

## Tasks to cancel / modify
CANCEL acceptance of ambiguous v1 identity as authorization for release execution. MODIFY positive release fixtures to newly approved v2 without weakening assertions; KEEP the exact v1 canonical vector for historical inspection. KEEP immutable-byte capture, approved handoff and old-writer gates for later independent integration, not as a workaround for bad identity.

## Compatibility impact
New signing_format enum value, unchanged CLI/API/result fields. Old approvals deliberately cannot execute; rejection uses existing safe statuses and zero-effect behavior. No auto-resigning or implicit legacy fallback. Operator signs a new immutable version after reviewing actual v2 contents.

## Migration impact
No DB/schema/config/data migration or pointer/receipt rewrite. Existing releases, receipts, backups and latest journal/memory remain. Source rollback does not authorize enabling weak v1 execution again.

## Correction verification
D56 local correction VERIFIED：15 identity RED→PASS、216 focused PASS、actual five source/readiness/data children、exact source reverse/reapply，以及 clean full scripts/check EXIT0／1,813 PASS。解除 FIX-020 source-format blocker，RI005仍PARTIAL/BLOCKED_BY_RELEASE_INTEGRATION；exact-head cloud另驗。[Acceptance](../evidence/FIX-020-2026-10-14/REPORT.md)。
