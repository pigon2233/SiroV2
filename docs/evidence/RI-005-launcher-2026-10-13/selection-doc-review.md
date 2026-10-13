# D52 final documentation consistency review

2026-10-13（Asia/Taipei）。Independent subagent; production, tests and root documents read-only. This task writes only `selection-doc-review.md`. No private data, credential, model, live service, or deployment was used.

## Result

**PASS after two DOCUMENTATION_ONLY corrections.** The 13 current documents, current RI-005 card and final REPORT distinguish the verified D52 source-selection/actual-origin/same-schema readiness slice from **RI-005 PARTIAL / BLOCKED_BY_RELEASE_INTEGRATION**. No new production change or test rerun was requested by this review.

The remaining package verify/import mutation window, first-adoption old/unmanaged writer absence, D50 CLOEXEC maintenance-to-runtime gap, exact approval/handoff, required migrations, wider ABI/dependencies/OS and formal deployment gates remain explicit. Source identity and healthy HTTP do not authorize release or certify the whole product. The freeze zones retain YELLOW for selector/launcher/Gateway and RED for live DB/migration/permission/publication. FIX-002/005/006 quality gates and scoped RT-011/013/015 DONE histories remain; the roadmap diff changes only the new current section and RI-005 current state/dependencies/status, not RT numbering or historical cards.

## Evidence checked directly

| Artifact | Raw result checked |
|---|---|
| `selection-before.log` | 70 FAIL / 1.09s; absent new API/type, not 70 separately reproduced old security defects |
| `selection-after-first.log` | 70 PASS / 0.51s, same frozen test file |
| `caller-before.log` | 10 FAIL / 2 PASS / 3 warnings / 0.98s |
| `process-final.log` | 3 PASS / 6.40s |
| `process-final.json` | 5 actual joined children: normal three SIGTERM exit -15 with shutdown complete; negative ABI/tamper two exit 1; exact source origins/digests/key-absent boolean and retained rows |
| `adoption-result.json` | 9 checks true, 3 controlled children joined/exit 0; new flock and SQLite write preflight do not stop the living old WAL writer |
| `focused-final.log` | 335 PASS / 3 existing warnings / 25.63s |
| `full-final.log` | 1,673 PASS / 5 real_provider deselected / 3 existing warnings / 199.58s |
| `format-final.log`, `lint-final.log`, `types-final.log` | 315 formatted files, lint PASS, mypy 250 source files |
| `rollback-final.json` | 273 baseline / 270 unchanged, exact 7 disposable reverse/reapply, source stable and no workspace data/index mutation |

The 95 new cases are 70 selector + 7 launcher + 15 readiness/DTO/owner + 3 actual-process cases; 1,578 prior offline cases + 95 = 1,673, and 240 adjacent existing cases + 95 = 335. All 11 current-section Markdown file links resolve locally. Schema/diff logs are empty as expected; this review reads the parent-owned checks and does not claim independently rerunning them. Unselected providers, aggregate scripts/check, human voice/comprehension/renderer, private current service, and deployment are correctly NOT_RUN.

Initial process fixture json/hashlib imports and rollback evidence field-name mismatch remain recorded as fixture/evidence defects, not production defects. Controlled account locator and origin telemetry in the signed fixture are disclosed; actual source import/HTTP/SQLite proof is retained and is not generalized to arbitrary generated code. The synthetic child lifecycle is distinct from stopping any real old SIRO process.

## Corrections identified and confirmed

1. The exact final process raw log is **3 PASS / 6.40s**, SHA-256 `544d6432a9648650cbf068e32fa02d5a970b2858ca23b89995548ad2329ffe58`. Its JSON/REPORT initially carried 7.58s from an earlier fixture run. The owning agents corrected final JSON/REPORT/review metadata to 6.40s; the original raw logs and production were preserved. The final JSON raw-log hash still matches the actual log.
2. The REPORT originally said every independent review bound all final sources. It now distinguishes final boundary/process/rollback binding, this final selector binding, and the **D52-before baseline** adoption probe. The unchanged D50 owner hash supports its specific old-writer counterexample; that probe never certifies all changed D52 sources or real first adoption.

No remaining current-section count, status, gate, evidence-link or scope contradiction was found at this cutoff. Earlier dated review paragraphs are preserved as historical evidence and do not override the current D52 section.

## Final selector and source binding

The final selector source/test hashes are identical to this agent's measured 70-case PASS. Every exact-seven entry from `source-freeze.json` was independently compared with the current filesystem before this report was written:

| File | Final SHA-256 |
|---|---|
| `src/siro/core/releases.py` | `0937b3b11b816e16fd7fa9876efc353e0cd64e91bc361bc9f3c71555920ce98b` |
| `scripts/launch_companion.py` | `fcfcf6072cb2078fbf9529644c7ee0a4937e81afd648b6499198cbb271b49790` |
| `src/siro/services/presentation/gateway.py` | `5d4de5e5ac458a0cde7ed1252eef99d352a6c8f8c681977bd2bf371a62b4d4d3` |
| `tests/integration/test_release_launch_selection.py` | `c4be0eaf7f64a9dd54d2906c870ae317bbcc7b7c9f6b836f3d002e481f9295f9` |
| `tests/integration/test_release_ready_identity.py` | `b25fe21dcd7b1939bccf749bfa7bad940203005f488e9fa08593bfcc69f7d00a` |
| `tests/integration/test_signed_companion_launcher.py` | `024b184518d346758039cb67971d01b11889e122f2de5a002084bdd9fe93639d` |
| `tests/integration/test_release_source_process.py` | `1d17acf98cc037b54bc12679ef668caf9bc32ab5db007bab7252f95cf3836c51` |

## Reviewed document cutoff

The following 13 documents plus REPORT were read at their current D52 sections (and the current RI-005 roadmap card). Any later change requires rechecking the affected claim; this is not permanent approval.

| Document | Reviewed SHA-256 |
|---|---|
| `docs/STATUS.md` | `b7bbe51e8c497c657472b19ab2aad20d3f58925e45cc76ea56969919ab08d1bd` |
| `docs/CONTRACTS.md` | `7f1de5a9bcfbef2e77d7c0974097304cf569c506cd439cf2da03547b5682df3f` |
| `docs/DECISIONS.md` | `d687fc1dc710df19c7138bf8a8e44fd6cc706d3ec6f359ce8660b729e6aba645` |
| `docs/runtime-evolution/ARCHITECTURE_REVIEW.md` | `920fdf0813530f14ef4a8a7bff2e81f72e70bc7ef9e48407904ca54993a77cd0` |
| `docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md` | `d8684636c3e01efb00c340f71eeaf9d098fafd56d5887871c652f8ab1a7697d2` |
| `docs/runtime-evolution/REGRESSION_BASELINE.md` | `9c5e620fb09d428b9f3414358796f15047ba74a2935b2f61f3d2886032b98a55` |
| `docs/runtime-evolution/COMPATIBILITY_PLAN.md` | `17a45cf2e90f0b95089dd1b9d7e76fd4c0bd88197c8d6e7d9dbc533366b300a5` |
| `docs/runtime-evolution/MIGRATION_PLAN.md` | `2ff56fb20a4996727b235d6b2b8e2df117a3591bd32384d4d376abbf67e9e716` |
| `docs/runtime-evolution/RISK_REGISTER.md` | `3f6a0369a70fd61f981fa2a4a502cc803af3710e2c7d24b4b766b329eb0bbdfa` |
| `docs/runtime-evolution/HERMES_GAP_ANALYSIS.md` | `d60d7b6f1da8563a6128f8c06506c54ce3220717e1928eb1941393360a51d7cb` |
| `docs/runtime-evolution/CAPABILITY_MATRIX.md` | `c159e909fc58b560482a9f0553085f1915554afec37fdf4c249ec3b5d7ea0da1` |
| `docs/runtime-evolution/RUNTIME_EVOLUTION_SPEC.md` | `c35a9e43feb1d51146752525ac1b08d4c0b1af61cd393ae50c360d12c0ab4e4f` |
| `docs/runtime-evolution/FIX_REGISTER.md` | `9319c3572bbb35b88e7b4ae1279066df84ddfbe3931194729299232980c170f3` |
| `docs/evidence/RI-005-launcher-2026-10-13/REPORT.md` | `559bf8fc8238d9a8e5ee82775eaaddc48c2cd98caf3d06b354c26ce41588c95a` |
