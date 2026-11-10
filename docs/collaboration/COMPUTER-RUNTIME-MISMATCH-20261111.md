# COMPUTER-RUNTIME-MISMATCH-20261111
Owner Grok Bot; IN_PROGRESS / LOCAL_ONLY / NOT PUSHED. Base36bbb806c6f22c8054dc6426554b45c963a5e5cb; main checkout override explicitly authorized by owner pt13u.
Read-only investigation FIRST: PID862 listens127.0.0.1:8000 with cwd AND PYTHONPATH pointing to computer-learning-20261107. Parent837/uv849 also old. Main has no grounded click_mark code. Launcher now points main, but start-companion reuses any healthy existing server. Play-SIRO is HTTP client only. No restart/config/input performed.
Owned: necessary small edits decision.py/http.py/scripts/computer-play.sh; new runtime-info/check and opt-in reply trace helpers; optional Claude semantic verifier; scoped unit tests/evaluation/docs. Excludes old worktrees, computer.env, launcher, running services, safety.py/main.js, shared STATUS/DECISIONS. Remote claim UNKNOWN; not a shared lock.
Default-off flags per new behavior; preserve allowlist, fresh window identity, emergency stop, no resend after unknown. WSL tests UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2; Ollama context8192. Do not invent missing frames/raw outputs or infer click-hold faults without evidence.

Checkpoint: core fixes unit34 pass (new25 + existing HTTP9), ruff/mypy8 source files pass, bash syntax pass. Full regression and offline verifier/click probes still pending: PARTIAL, not live acceptance. All validation uses fake transport or frozen images, never ComputerBridge execution. The serving old gateway and user computer.env are untouched. Diagnostics include only PID/source path/class chain; raw trace adds already-allowlisted observed bytes only with BOTH trace and dump flags; limit400 records, secret-pattern redaction, errors preserved before retry folding. Claude verifier is separately opt-in and bounded Read-only cloud call; unknown/error never confirmed. Existing prompt text unchanged. Three pre-existing http lint issues cleaned by equivalent wrapping/boolean expression only.

## Read-only findings / proven versus unknown (Asia/Taipei)

Rechecked2026-11-11 01:13:36+08:00: serving PID862 cwd remains computer-learning-20261107; port8000 belongs to862. PYTHONPATH also pointed at that worktree. No main gateway; no service restart/config change was performed. Play-SIRO.cmd only calls the HTTP client. start-companion reuses ANY healthy server at8000. Updating launcher checkout does not replace the running process.

Actual mode was old LocalGroundedDecider, SIRO_COMPUTER_DECIDER=ollama-grounded, gemma4:e4b. The literal grounded click_mark comes from old local_grounded.py, absent in main. It numbers image-dependent target regions;29/26/33 have no stable semantic identity. Generic expect and hardcoded confidence0.9 are old implementation properties, not evidence the intended button was chosen.

Safe env listing (including duplicates, last value wins) is runtime-investigation.json. Effective file values: CLOUD_SCREEN=1, AUTONOMOUS=1, ENDLESS=1, MAX_STEPS/SECONDS/SEGMENTS=0, PLAYBOOK=0, DECIDER=ollama-grounded, OLLAMA_MODEL=gemma4:e4b, ACCESS=desktop, COORD_GRID=1, OLLAMA_NUM_PREDICT=150, GROQ_MODEL=qwen/qwen3.8-27b, GROQ_REASONING=low, PERCEIVE=auto. All names have SIRO_COMPUTER_ prefix. TOKEN is REDACTED. Running process instead has PLAYBOOK=1 and no PERCEIVE; no ALLOWED_PROCESSES nor new A-D flags in either file/process. This is stale configuration, not a request to copy old desktop-access bypasses into main.

siro.log: run200 at2026-11-11 00:56:19.546+08:00, after state calls00:55:44.686/00:56:04.411. Access logs contain no frames, numbered atlas, raw model text or parse exception. Searched runtime data/log directories, old worktrees, main .siro-data, profile siro-computer and Pictures/Screenshots; no frame from this run saved. Newest Pictures frame predates run. Existing profile overlays are previous offline work, not new run evidence. Therefore ZERO new real-run frames added; exact bad_model_output causes and target29/26/33 elements are UNRECOVERABLE from saved evidence. Old code folds not_json/illegal IDs/bad operations/transient failures into generic wait; length truncation is possible, not proven.

All four reported coordinate mappings exactly match image_to_screen at960x520,rect[0,0,1920,1040],desktop1920x1080; four new pure tests verify this.1040 may exclude40px taskbar, but no evidence warrants adding an offset. sent proves transport only. Cannot distinguish wrong target / focus or game registration / semantic verifier failure; no claim about required hold/double click, and no guessed input timing fix.

## Fixes and boundaries

Core checkpoint ca14a34a0306baefb905f2e210d07197010372d0:
- scripts/computer-play.sh + new computer_runtime_check.py: SIRO_COMPUTER_REQUIRE_CHECKOUT=1 checks authenticated status loaded-source identity BEFORE countdown/run POST. Old/missing/mismatched identities fail closed. Config lookup does not export tokens. Fake-curl shell integration proves only GET status occurs on failure.
- http.py + runtime_info.py: SIRO_COMPUTER_RUNTIME_DIAGNOSTICS=1 exposes actual loaded decision module/source root, PID and wrapper chain through existing authenticated local status route. Does not enable control or expose environment secrets.
- decision.py: SIRO_COMPUTER_STRICT_BACKEND=1 rejects unsupported ollama-grounded rather than silently falling back to weak plain pixel Ollama. Known aliases unchanged.
- reply_trace.py / decision.py: SIRO_COMPUTER_TRACE_REPLIES=1 AND existing DUMP_FRAMES path save observed allowlisted frame SHA/geometry/window identity/raw parsed-provider text/exact parser error before retry folding; max400 records, bounded/redacted text, no writes for secret/blocked/unallowlisted frame, IO failure cannot change action semantics. Does not capture network/envelope errors or old grounded atlases. Private evidence should stay outside repo.
- Independent latent issue in main: Claude verify was ALWAYS unknown (claude_verify_not_used), so even correct changed-screen clicks could accumulate unresolved stops. SIRO_COMPUTER_CLAUDE_VERIFY=1 adds bounded read-only CLI semantic verification against expected result/current frame with existing cloud-screen consent. Tools restricted to Read; no session persistence; CLI config allowlist same as decide. Failure/invalid/unknown never confirmed; cancellation propagates. NOT a proven cause of the OLD grounded run.
- All flags default OFF. safety.py, Ctrl+Alt+Shift+Esc registration, allowlist authorization and default-off unchanged. No whole-file rewrite, no old scene patches imported, no real input, no configuration/launcher edit, no backend restart. Remote state/claim UNKNOWN. Local main override owner-authorized.

## Offline evidence (reproducible; not real play acceptance)

Original20 tasks /5 unique images, manual_visual_review labels,15 text +5 no-text; manifest SHA256914077f0196b22cb93dc08413668656f478e7066c097a683c740ec46c350a00a unchanged. Zero new run frames available. Development set, not held-out. All measured errors/misses retained, no cherry-pick retry.

| Probe | Result | Mean / median seconds |
|---|---:|---:|
| Claude pixel previous checkpoint |20/20|5.59 /5.39|
| Claude pixel THIS rerun |19/20|5.86 /5.73|
| No-text THIS rerun |4/5|5.88 /6.00|
| New verifier, static true/false scene predicates |10/10|5.19 /5.15|

THIS rerun pixel miss: combat-draw-icon chose End Turn instead. Decision prompt/routing unchanged except opt-in tracing, so19 versus20 is observed variability, NOT improvement or proof of regression. New computer_verify_eval.py derives10 positive/negative scene predicates from existing manual scenario metadata; it proves static predicate recognition only, NOT before/after transitions, game registration or real play. Verifier latency is an EXTRA model call, not included in pixel timings; no measured live step latency is claimed. No new Ollama/Groq measurements; prior A-D results remain in prior handoff, no invented numbers. Every ad-hoc Ollama inference in prior work used8192; none sent this task.

Commands and complete results: runtime-mismatch/{checks.json,unit.txt,regression.txt,ruff.txt,mypy.txt,bash-syntax.txt,claude-pixel.json,claude-verify.json}. All uv tests/eval in WSL with UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2. Offline measurements bounded20sec/item and240sec/run, no automatic retries. stdout logs are saved too. Real devices never invoked by evaluator; unit/integration inputs are fake.

## Exact owner-only next-run procedure (NOT executed)

1. Edit computer.env yourself: remove duplicate decider/flag entries; preserve TOKEN, do not paste it into chat. Replace ollama-grounded with supported claude. Do not use old ACCESS=desktop to bypass whitelist; remove stale ACCESS/PERCEIVE lines (main does not implement them). Set the lines below exactly once. Existing cloud consent is required for Claude; private screenshots/replies remain local except explicitly opted-in model image requests.

```dotenv
SIRO_COMPUTER_DECIDER=claude
SIRO_COMPUTER_CLOUD_SCREEN=1
SIRO_COMPUTER_CLAUDE_VERIFY=1
SIRO_COMPUTER_ALLOWED_PROCESSES=slaythespire2.exe
SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES=1
SIRO_COMPUTER_STRICT_BACKEND=1
SIRO_COMPUTER_RUNTIME_DIAGNOSTICS=1
SIRO_COMPUTER_REQUIRE_CHECKOUT=1
SIRO_COMPUTER_TRACE_REPLIES=1
SIRO_COMPUTER_DUMP_FRAMES=/home/pepepig/.local/share/siro/data/computer-diag-20261111
SIRO_COMPUTER_COORD_GRID=1
SIRO_COMPUTER_PLAYBOOK=0
SIRO_COMPUTER_AUTONOMOUS=0
SIRO_COMPUTER_ENDLESS=0
SIRO_COMPUTER_MAX_STEPS=10
SIRO_COMPUTER_MAX_SECONDS=120
SIRO_COMPUTER_MAX_SEGMENTS=1
SIRO_COMPUTER_OCR_NUMBERED=0
SIRO_COMPUTER_REGION_NUMBERED=0
SIRO_COMPUTER_REGION_PIXEL_FALLBACK=0
SIRO_COMPUTER_REGION_GALLERY=0
SIRO_COMPUTER_ACTION_BATCH=0
SIRO_COMPUTER_SCREEN_GUARD=1
SIRO_COMPUTER_CONTROL_ENABLED=0
```

Strict pixel SCREEN_GUARD=1 can safely refuse animated screens (screen_not_restored); do not disable safety gates or retry input blindly if it does. That limitation was NOT tested by the static click benchmark. This is a bounded supervised diagnostic configuration, not a promise of uninterrupted autonomous game play.

2. Choose tray 'End SIRO INCLUDING SERVICE', NOT pet-only exit. Equivalently user may run WSL ~/.local/bin/siro-stop. Check it confirms stopped and no8000 listener remains; if it says still responding, do not start Play or assume restart succeeded. Ask for help with that specific stop failure. Do not manually kill guessed PIDs.
3. Restart normally with corrected ~/.local/bin/siro-companion-vrm (confirmed main checkout, PYTHONPATH main/src and UV_PROJECT_ENVIRONMENT=/home/pepepig/.venvs/sirov2). Restart native desktop too so whitelist-name code reloads. Launcher edit alone never replaces an already-healthy old backend. We did NOT do any of this ourselves.
4. On fresh desktop explicitly enable existing tray control, keep emergency stop available, bring game front yourself and invoke the same bounded Play-SIRO command. It must print 'Backend checkout verified' BEFORE countdown; if missing identity/mismatch, no run is sent. If still stuck, preserve private diag folder and new console output; it now records original frame/geometry/raw reply/parser evidence for pixel route. Do not claim game input was accepted just because sent printed.
5. After diagnosis turn TRACE_REPLIES=0 and remove/clear DUMP_FRAMES; local private diagnostics can contain game-screen text. No changes are applied by this task.

## Remaining acceptance

Core deployment/configuration hazards and main Claude semantic-verifier gap fixed in main, but live acceptance BLOCKED pending owner restart and supervised test. Missing old frames cannot be recreated honestly. Wrong element/focus/hold/DPI/verifier causes for prior run remain unknown. Static predicate probes do not resolve them. A-D work is already committed and not redone; hybrid/batch remain experimental/off. No promise that control has no problems. Disable new flags to revert optional behavior; no reset/clean/rewrite needed. LOCAL_ONLY / NOT PUSHED.

## Final checks on this exact tree

- Unit44 passed (35 new tests +9 existing HTTP tests).
- Full computer-use regression394 passed,4 SAME pre-existing failures; exit1 retained. No deletion/skips or relaxed tests. Fixture screen.png vs production screen.jpg; expected transient CLI retry; missing_expect in old action fixture; history saw: vs saw=.
- Ruff and mypy9 source/test files passed; bash -n passed. Full-project lint/type checking NOT claimed. Existing FastAPI/Starlette TestClient deprecation warning remains.
- Runtime loaded-source guard proven with fake HTTP; all new provider calls in tests are fake; actual cloud offline pixel19/20 and predicate10/10 only read frozen images. No real input, stop/start, env/launcher modifications, or Ollama requests by this task.

Final evidence commit SHA is the output of git log -1 --format=%H -- this handoff; same-commit self-reference deliberately omitted. After explicit staging/commit, working tree expected clean; actual status reported in final delivery.
