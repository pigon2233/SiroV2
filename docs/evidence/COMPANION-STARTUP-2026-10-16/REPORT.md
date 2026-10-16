# Companion startup repair and current product readiness

Date: 2026-10-16. Verdict: **usable web integration candidate; complete desktop companion NOT delivered**. This repair is not whole-product release approval.

## Root cause and change

Owner's literal hello response exactly matches OfflineDemoModel's NO_SOURCE branch. Raw `siro-gateway` does not read `.env.local` or discover the renderer. README and `scripts/start` directed owners through that low-level entry; the service installer did likewise. Local configuration already names Groq GPT-OSS20b and licensed Cubism/Haru assets exist. Before repair no current listener at 8000/8026 was detected; the user's prior invocation itself is not known, but raw-entry behavior and literal response match.

- `scripts/start PID_FILE` now calls existing configured `launch_companion.py`; `--demo` explicitly retains isolated old behavior. Relative PID paths are anchored before changing to project root.
- Installed user-service ExecStart now calls project Python + same launcher. Existing installed units are not silently rewritten/enabled.
- Raw gateway stays available for compatibility. Offline/placeholder configuration has an accessible, persistent notice explaining fixed demo replies and the product command.
- README/operations/quickstart identify the product entry. No greeting hardcode, fake emotion, automatic create_app asset selection or memory change.
- HTTP transport records only numeric non-2xx status. No URL/header/body/prompt/credential logging; original HTTP exception and retry rules preserved.

## Current real-service checks

Started configured product at http://127.0.0.1:8000/ using existing normal data. Consistent local SQLite backup made first; schema 14 before and current schema 14, no migration required. Backup and service logs remain ignored/private. No private history exported. Service remains running for owner testing, browser marked deliverable and reconnected after diagnostic restart.

- health/ready: healthy.
- Authenticated runtime: candidate; cloud:openai/gpt-oss-20b; local:qwen3-tts-0.6b-base:anime-daughter-v1; workspace/summary/organization/goal_tasks enabled. Enabled does not equal all feature acceptance.
- True browser at /live2d/: Haru visibly rendered, “Live2D 已就緒”; no placeholder.
- True UI hello: “Hey there! How can I help you today?” (Groq, not deterministic demo).
- True UI read-only OS command: actual `cat /etc/os-release` exited0 and result visible in Computer; continuation FAILED with HTTPStatusError.
- Separate isolated actual main/Core/SQLite + real Groq same synthetic OS goal: two HTTP200 requests, COMPLETED. No private data used.
- Repeat synthetic OS goal against running service: effects had observations but final FAILED; safely logged **HTTP429**. This confirms rate limiting for that repeat, not the status of earlier uninstrumented failures. Do not claim all earlier failures had the same cause or that the workflow is reliable.
- Preliminary 64-token connectivity probe returned HTTP200 with empty content: not conversational acceptance and not counted as PASS.

## Product matrix

| Area | Current conclusion |
|---|---|
| Web frontend | Nine separate hash work pages and real API/WS handlers exist. Browser chat, model response, renderer and Computer result visibly tested. Entire UI not fully accepted. |
| Text model/backend | Real configured provider and authenticated Core/SQLite path work; continuous tool continuation currently encounters provider429. Not reliable complete agent acceptance. |
| Live2D | Real web renderer works. **Independent transparent desktop window, free roaming, walk/play/rest assets and platform hit testing are not implemented/accepted.** Web character is not VPet. |
| TTS/STT | Configured real pipelines exist. This turn did not test microphone or listen to voice; historic FIX-005 remains PARTIAL for speed/human listening. |
| Memory/summary/organization | Runtime callers and sourced mutations exist. Not revalidated by private-memory edits this turn; no claim of emergent memory/personality. |
| Computer/browser | Real read-only argv executed and results preserved; provider continuation stability unresolved. Full arbitrary desktop/sudo not accepted. |
| Tasks/skills/self-update | Limited approved document/checklist capabilities exist. General autonomous learning, completing arbitrary TODOs and self-release remain incomplete. |
| Physical devices | Out of this repair scope; real hardware acceptance still separate. |

RT-013/015/RT-011 summary were completed in their limited 2026-10-06 slices; old DEFER wording is historical, not current blockers. VPet requirement and speech/reliability gaps are real remaining work.

## Automated evidence

- entry-tests.log: 14 PASS, configured/signed launcher and operation compatibility.
- related-tests.log: 72 PASS, adapter/stream termination/retry/integrated/entry behavior. This preceded the extra default-script refusal case and only later test typing was adjusted.
- operational-final.log: 5 PASS, including real default script refusing missing model before DB creation, and explicit demo start/stop health/PID cleanup.
- adapters-final.log: 43 PASS, including HTTP status logging with zero request/response content and no emitted data on error.
- Renderer subagent: gateway/frontend_companion/launcher/signed_launcher 38 PASS, 3 existing warnings. Readiness subagent: frontend_navigation + frontend_speech_cancel 32 PASS, 7.12s. Counts overlap; do not add as unique test count. Their checks did not operate private service/data.
- mypy-final.log: 268 source files PASS; scoped Ruff and shell syntax PASS. An initial new-test mypy export error was fixed; final recorded result supersedes it.
- Full repository test suite, remote CI, real TTS/STT/human hearing, native desktop, soak and deployed rollback NOT VERIFIED this turn. Historical 2129 PASS is not this turn's whole-product proof.

## Compatibility and rollback

No API/schema/state/privacy/grant/release-selection changes. Offline explicit development entry retained. Do not revert to an older DB after normal use. source.patch/source-digests record only owned source/tests against the current local HEAD; revert these source edits only after stopping owned runs, preserving new journals and unrelated concurrent changes. Read-only backup is recovery insurance, not an automatic rollback step. No deployed rollback was exercised.

## Required next work

1. Treat Groq429 as a provider availability/budget limitation; preserve completed effects, add a bounded designed recovery path with separate acceptance rather than repeatedly replaying owner commands.
2. Implement and test native desktop host from COMPANION_EVOLUTION_PLAN (transparent window, single renderer/audio owner, character hit region, focus, Wayland behavior), then motion assets/free activities. No claim that opening a browser window meets VPet requirement.
3. Revalidate voice latency/completion/human listening and combined product flows; keep incomplete product gates visible.
