# Read-only push scope audit — 2026-10-13

Candidate scope/scan were reviewed offline; no staging, commits, push, production/test/document edits, private runtime or local Codex settings, media or network reads occurred. Only push-review-* artifacts in this directory were written.

Candidate:1111 paths. Initial reduced scope:1061 paths after excluding50 raw scan/review outputs and next-card RED backup test. Latest exact fingerprint binding:4581 findings;{'ACTUAL_REPOSITORY_GIT_COMMIT': 15, 'ACTUAL_PUBLIC_ARTIFACT_SHA256': 4408, 'UNRESOLVED': 106, 'EXPLICIT_SYNTHETIC_BASIC_AUTH_NEGATIVE_FIXTURE': 1, 'EXPLICIT_SYNTHETIC_TEST_CREDENTIAL': 5, 'DERIVED_ACTUAL_PUBLIC_LITERAL_SHA256': 17, 'EXACT_PREVIOUSLY_REVIEWED_FINGERPRINT': 29}.

106 findings across47 files still require artifact binding. File/line/type/fingerprint and safe JSON field paths are in push-review-unresolved-fields.json; no flagged values or original lines are emitted. These are largely named source/text/audio/prompt/settings/UI digests, not demonstrated secrets. Existing fields alone are not treated as proof.

A conservative scope excludes every file still containing an unbound finding and is provided separately. It omits part of the historical evidence archive; retained local reports may refer to omitted evidence. It is a choice for root to assess, not staging authorization.

Concurrent source annotations changed public file SHA values while original candidate scan/scope remained unchanged, increasing some historical baseline mismatches. Preserve/capture exact pre-annotation bytes to recover independent bindings. Do not silently approve all Hex detector results.
