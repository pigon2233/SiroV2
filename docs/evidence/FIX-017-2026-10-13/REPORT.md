# FIX-017 — optional voice SDK stays behind the owner boundary

Status: LOCAL_FOCUSED_VERIFIED / complete regression and exact remote head PENDING.

Actual GitHub run38389536976's blocked Gateway process emitted ONNXhardware discovery before the required Busy error. Independent fresh-process importguard proves presentation→Gateway→TTS→Kokoro→ONNX occurred before any data-owner acquisition, and a broken SDK could prevent the Busy message. Confirmed existing IMPLEMENTATION_BUG/MISSING_INTEGRATION/TEST_GAP, REQUIRED_FIX/MEDIUM; D50 invariant remains correct. This is one production leaf repair, not a reason to redesign Gateway/owner/providers.

D54 captures the decision before implementation. Only tts.py moves Kokoro's type import under TYPE_CHECKING and its runtime import into existing _render_sync model-is-None branch. Model constructor, create args, phonemes, voice mixing/energy, caching, original lock/cancel/error behavior remain. No Gateway/owner/oldtests/deps/version/logging change; no warning mute or softened Busy assertion.

Five fresh-process tests: original5FAIL/3.39s→after5PASS/4.13s. Final related audio/plan/completion/actualGatewayowner34PASS/2existing pypinyinwarnings/7.71s. Positive SDK/model are synthetic stubs: actual worker-thread/import/cache/error wiring is exercised; no real models/voice/GPU. Controlled async cancellation preserves the original wait semantics and joins the controlled worker; does not certify interrupting blocking native inference. Ruff format/lint/strict typing2files/scoped diff PASS.

Exact two-file disposable reverse/reapply SHA PASS; before TTS restored, newtest removed then both reapplied, no data/Git changes. baseline305 captures the public2324b35 source; simultaneous FIX-016 workflow/quoted-key fixture changes are separately documented. Final full nine-file combined clean-archive scripts/check and supportedUbuntu26.04 Actions are PENDING. Source rollback reopens the owner pre-init gate; no live rollback/deployment performed.

Overall architecture YELLOW. This repairs eager provider initialization leakage and restores the original boundary; no new loader, registry, owner manager or intelligence abstraction. Audio remains YELLOW pending product voice quality/performance; synthetic tests GREEN; liveDB/permissions/release RED. RI-005/006 onward still BLOCKED_BY_FIX until complete acceptance, original RT DONE history intact. No live8026/privateDB/chat/WAV/key/config/model/GPU access. Codebase Memory unavailable; reindex NOT_RUN.
