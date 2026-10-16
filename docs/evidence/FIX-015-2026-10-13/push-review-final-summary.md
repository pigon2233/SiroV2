# Publication scope review — 2026-10-13

1691 recommended public paths, additional132 older historical evidence/verification files held local. Whole docs/runtime-evolution/verification subtree is excluded. No production or active test source is excluded except root's already excluded pending FIX015 RED test. SOURCE_INVENTORY.json held local because9 old captured hashes are not artifact-bound.

6 remaining findings all refer to the mandatory gpt_oss_profile.json pinned revision and five public tokenizer/config/LICENSE checksums. Root will verify those official small public artifacts before publication; this audit does not claim that network verification.

All nondigest test findings are individually bound to explicit synthetic literals and exact detector fingerprints. API keys are synthetic constants in fixtures/captured fixture logs; BasicAuth is synthetic-password on the ephemeral local negative fixture. No blanket keyword or entropy exemption.

Only127 paths exactly match existing remote5d83 blobs; none of original flaggedfiles matched remote unchanged blobs, so old local history was not treated as alreadypublic. Candidate files and old review metadata were read, no private ancestor blobs, runtime/models/audio/localsettings were read. No staging, source/test/docs changes, commit or push occurred.

This checkpoint deliberately omits some local historical raw evidence. Preserve original local history and files separately; do not claim a complete remote historical evidence archive. Root should publish a nonforce child of existing remote public parent without private local ancestors, as planned.
