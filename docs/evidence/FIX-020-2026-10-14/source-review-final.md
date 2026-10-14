# FIX-020 final fixture, source and rollback verification

2026-10-14（Asia/Taipei）。Local self-owned synthetic verification only; no private data, live8026, real providers/models, release deployment or Git commit/push.

## Frozen source and preserved gates

Final releases.py SHA256 is `c959036b436e817d96db14a971b430c02b2b8c096dee00586e3cdf98de36003e`; final independent launch-fixture helper SHA256 is `b58abb536a5156661ec42c77d911672a9233b4971c1288653f7cb85785958e86`.

Against baseline f3f94c12, existing function ASTs changed only `ReleaseManager._verified`; new method is `_digest_v2`. Original `_digest`, `signing_payload`, stage/rollback/selector/schema/healthcheck functions are unchanged. Literal parsing additionally admits explicit v2. `_verified` rejects v1/None before hashing source, then verifies the complete v2 payload and framed source digest; it never automatically rewrites an approval. Resource/filecount/Path.parts framing follows D56; empty directories, permissions, native dependencies and hostile mutable filesystem races remain outside this file-identity repair.

Seven existing positive fixture preparations explicitly use new v2 approvals; their 196 assertion ASTs are preserved, with only the authorized source-process digest algorithm selection normalized. Canonical v1 fixed bytes/HMAC and the legacy schema-tamper negative function remain exact. The final launch-selection helper independently implements framed-wire hashing and calls no production digest helper. Unknown-format input is v3 so its rejection assertion remains meaningful. `fixture-preservation-final.json` and `production-preservation-final.json` bind these checks to final bytes.

Current v2 implementation against old positive fixtures produced **42 FAIL / 111 PASS / 48 ERROR / 11.24s** (`positive-fixtures-red.log`). This is a fixture compatibility transition, **not** the original digest-defect RED. Initial fixture pass 201/21.40s used the superseded direct helper and is not final acceptance. After restoring independent framing, seven fixture files plus the 15 new identity cases produced **216 PASS / 2 existing pypinyin warnings / 22.70s** (`positive-fixtures-final.log`). No assertion, effect, timeout, owner, privacy or latest-data gate was lowered.

## Source-only reverse/reapply

`rollback-probe.py` copied only public source, the new identity test and pyproject into a disposable temporary root. The one-file `production-repair.patch` was checked and reversed with Git; resulting releases.py exactly matched baseline `0937b3b11b816e16fd7fa9876efc353e0cd64e91bc361bc9f3c71555920ce98b`. All other 136 copied source files remained unchanged.

New identity tests against the reversed source reproduced **15 FAIL / 0.34s**. Reapply-check/reapply succeeded, restored the exact final hash and entire copied source map, and yielded **15 PASS / 0.16s**. Child test processes joined, temporary root removed, and real workspace source stayed unchanged (`rollback-result.json`, step logs).

This is a technical source-reversal proof. Operational rollback means withdrawing release execution before reversing source; it does **not** authorize v1 execution, automatic re-signing, receipt migration, old DB restoration or deployment. No production rollback was executed.

## Actual v2 source-process behavior

A separate final run of the existing `test_release_source_process.py` with stdout enabled produced **3 PASS / 7.36s**. Three emitted JSON cases are captured verbatim in `actual-source-process.json` and source-bound to the final releases.py hash.

- Three normal children actually loaded signed source versions **1.0.0 → 2.0.0 → 1.0.0**, with real loopback HTTP ready version/digest, selected package/Core/Gateway origins, signing key absent, unchanged package bytes, SIGTERM exit -15 and shutdown-complete/joined.
- Late writes after joined children remained after code-only rollback: conversation, memory, completed ledger and fixture each retained all three batches; actual schema prefix stayed 13.
- Unsupported DTO ABI and source-tampered package each refused with exit1, no host-source fallback or DB byte change; both refusal children joined.
- All owned temporary roots were removed. Fixture account interposition is signed synthetic instrumentation; readiness/server/IO were actual process integration, not mocked results.

Mutable verify-to-import windows, old/unmanaged writer absence, approved maintenance handoff, arbitrary native dependencies/ABI, power loss and formal deployment still require their own RI-005 gates. The complete clean-check and exact-head cloud results belong to root's final acceptance; these local scoped results do not substitute for them.
