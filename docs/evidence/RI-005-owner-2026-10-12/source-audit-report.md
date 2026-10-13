# D50 final source and public evidence audit

Status: **PASS for D50 owner/FIX-014 scoped slice; FIX-015 cleanup remains FAILED_VERIFICATION**.

Root directly traced the exact captured pre-card CLI/Gateway to final ownership plumbing. The only existing source changes are CLI and Gateway composition; one new lower OS adapter owns canonical resource descriptors and captured default pools. Core, SQLiteStore (including D49), operations, releases, SQL/schema, launcher/scripts, grants, providers, voice, UI and dependencies remain unchanged from the268-file baseline except these two expected source paths. No circular/lower-layer leakage or global owner registry was introduced.

| Final path | SHA256 |
|---|---|
| src/siro/cli.py | `cd78a622bd99d7779761cfbf29bdc04dab4ddccac8e45fcc6a84c85457a24a1f` |
| src/siro/services/presentation/gateway.py | `8be67a5d3aeff067f00c49db1ac1b19ab3e6ba22c6c9c9911fa2b3adf2db3dd1` |
| src/siro/adapters/data_ownership.py | `3f87e47eaa5622d51f1ff6a08ad2653fbdd39ff0955c52f0868ea999295fe77d` |
| tests/integration/test_data_owner_callers.py | `0e2a66c8143b8ba3897ef41053189ab707cdcd55daa4aee806060f1ce6ee84c0` |
| tests/integration/test_data_owner_lifecycle.py | `6418c5b0176d693fc5a76cbf9ad750964284bf50e08bdc25fcfc8599d6ac8418` |

Exact patch identity is `a6211afa1caac08f8d70adf4f59a30fe67493d3275eac56ca1816a6869a9de3f`. `preservation.json`/`preserve_and_rehearse.py` prove266 unchanged existing files, current5-path binding and disposable source-only reverse/check/reapply equality; temporary rehearsal workspace removed, live source never reverted, all data preserved. Current full1553PASS/5deselected157.81s and focused215PASS10.58s bind these bytes; whole format309/lint/mypy243/schema/diff pass. Independent contract and actualOS reviews bind the same5paths, preserve historicalREDs and separate70/16 selected runs from root full regression. Lifecycle reviewer finalturn usage limit is not independent finalapproval.

Actual final3-key ZIP backup-stage probe joins before handing off every lease but discovers staging recreation; FIX-015 REQUIREDFIX/MEDIUM is explicitly planned/blocked, not silently debt or completedcleanup. Actual initialdir0700→recreated0775, DB/WAL/SHM0600; no measured otherUID contentread. Root's actual synthetic connection-context observation confirms transaction context does not close SQLite connections. No new architecture correction/backup manager is required.

Public source5/docs12 findings0; evidence87 inputs/322 raw findings: 321 exact recordedpublicSHA256 falsepositives and 1 individually verified generatedsyntheticpath falsepositive, unresolved0. Cutoff2026-10-12 12:00:13 UTC; output reports/helper/individualreview registry and later result-only annotations excluded by explicitlist. No blanket entropy exemption/network verification/private data read. Each digest finding is bound to a computed public artifact/baseline or an individual exact historical field; the path finding matches the exact recorded removedsyntheticroot/staging entry and detector fingerprint.

No live8026/restart/private DB/chat/WAV/config/key/model/GPU/service release/deployment. Runtime/version/adoption approval/handoff, ZIP cleanup, arbitrary library/raw/oldwriter behavior, hostilepath races/networkFS/powerloss remain outside the certified owner profile. This scopedPASS is not productdeployment approval.
