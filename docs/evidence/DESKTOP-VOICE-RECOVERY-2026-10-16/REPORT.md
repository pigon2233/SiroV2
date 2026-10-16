# Native desktop, voice first segment, rate-limit recovery

Date: 2026-10-16 (Asia/Taipei). **Delivery is partial overall.** Independent native presentation and bounded rate-limit recovery are implemented and locally checked. Full VPet activities and GPU voice/human-listening acceptance are not complete.

## Native presentation

Added desktop/host.js, input-mask.mjs and original SVG icon; scripts/start-companion, start-desktop, install-desktop. Existing backend remains the only Core/SQLite/tool owner. start-companion starts a configured backend only when needed and refuses an offline demo, then starts one GtkApplication. A second invocation exited0 while only one host PID remained. Closing/minimizing the host does not terminate the backend or erase data. Local application-menu entry org.siro.Companion.desktop installed; no login autostart.

Installed system GJS1.88 / GTK3.24.52 / WebKitGTK2.52.6 (GI API4.1), no Electron/Python GUI dependency. WebKit sandbox queried enabled. Exact loopback URI and existing Origin/session auth required; remote/file/null origins and arbitrary native shell/file IPC not added. Native bridge only chat/focus, this-window drag, control center, minimize and quit. Audio-only permission prompts require explicit owner response; other permissions denied. Control center uses existing nine-page frontend without a second body/audio owner.

/desktop shares the existing frontend and handlers, transparent CSS, click-character chat bubble and visible stop/control buttons. /ws/body accepts optional presentation='desktop', gives live desktop priority and clears ownership before awaited disconnect cleanup; explicit web attachment after exit restores latest emotion only. SDK repair adds terminal handoff notices and stops reconnecting replaced renderers. Desktop-only frame cap24; ordinary web timing unchanged. Alpha-derived native input region updates every3seconds, resize/monitor coordinate paths remain presentation only. Temporary pixel snapshot is solely this app's own WebView, never the desktop screen; scratch is bounded and deleted on normal shutdown. Optional diagnostics save at most three avatar snapshots while chat is closed, never chat screenshots.

Actual source-matched native process at right-bottom (1530,480;360x570) against normal8000 backend: ready=true, alpha=true, sandbox=true, about36% native input coverage, latest host-source hash matches. Avatar snapshot has substantial zero alpha. Exported native-verification.json records the facts and limits. Actual viewport screenshot stays ignored at .siro-data/verification/desktop-product-20261016/pet.png (licensed character image is not added to Git). Initial type/property bug web.is_loading() was found by actual launch and fixed to property; old logs remain private. Normal SIGTERM exits cleanly and clears the owned renderer.

**Not verified:** owner mouse drag/click-through feedback, all monitor/DPI/fullscreen/lock behavior, native Wayland. This GNOME Wayland session uses explicitly announced app-only XWayland compatibility; login session unchanged. **Not implemented:** editable full-body leg rig and walk/sit/play asset suite, free roaming. Haru has no usable leg parameters; no sliding stand pose is misrepresented as walking. Overall desktop activity card remains PARTIAL.

## Voice

Original qwen3-siro-anime-daughter-v1.wav reference unchanged. First segment is separate <=24characters with natural sentence/clause boundaries, later segments remain <=80. Canonical text stays exact and bounded; completion/EOS/cap checks, one worker, cancellation/reap and at-most-one prefetch retained. Planner/worker segment-version fingerprint synchronized. Synthetic157-char story first segment56→16, still3segments; this is workload reduction, not measured speed. NewCPU cases were RED then PASS; focused148PASS and source-only byte rollback in FIX-005-first-segment report.

**GPU benchmark blocked before inference.** nvidia-smi exit9; Torch buildCUDA13.0 reports cuda_available=false; /dev has nvidiactl but no nvidia0; lspci identifies RTX3050Mobile with no NVIDIA graphics driver in use. Current kernel7.0.0-38, installed precompiled modules only through-34. Official Ubuntu repositories offer matching signed595-open modules. scripts/repair-nvidia-kernel prepares the matching driver/module install plus modprobe; apt-get simulation resolved successfully. SecureBoot stays enabled, no reboot commanded. Real installation was NOT RUN: sudo -n reports interactive authentication required. Owner must execute the prepared script in their own terminal and enter password there. No password requested in chat.

No new worker/WAV/throughput numbers were fabricated; GPU-only harness refused non-CUDA-ready host, no worker remains. Human listening NOT RUN. FIX-005 stays PARTIAL / GPU_DRIVER_BLOCKED. A shorter first segment cannot fix cold model load or guarantee fluent later gaps.

## Rate limiting

Optional FailoverModel rate_limit_max_wait_seconds/clock/on_retry preserve old defaults. Configured product launcher explicitly enables one additional cloud attempt; raw gateway remains disabled by default. On pre-emission429, wait valid Retry-After seconds/date within60seconds then retry the SAME provider once, with unchanged payload/goal/permissions/observations. UI shows safe delay and stop. Text/tool/finished or buffered tool intent prevents retry. Cancellation also cancels and joins notifier/wait. Groq daily remaining-requests0 and over-cap waits fail closed; another429 still fails. This does not increase free quotas or guarantee provider availability.

Actual main/Core/SQLite + real controlled Python tool marker: tool finishes once, continuation429 then retry completes, selected-provider metadata survives readback; cancellation while waiting issues no extra request; disabled profile retains old failure. A true loopback HTTP429→SSE200 case confirms payload equality and requested time spacing. Terminal fences include retry notices; cancelled/failed/delta clear the notice without action replay. Notice uses source session/stream and numeric delay only, never prompt/header/body/key.

## Tests and repairs

- full-final.log: **2225 PASS,5 real-provider deselected,3 existing warnings,250.34s**. This is offline automatic regression, not full-product or real cloud/voice acceptance.
- Initial full-offline.log:2220PASS/5FAIL (ReferenceError in sliced legacy speech-cancel harness after new helper placement). Helper moved into shared speech helper region, standard DOM marker used and new minimal rate-notice fixture supplies DOMStringMap. Existing cancellation assertions retained. Focused11PASS and final full2225PASS supersede initial failure.
- targeted-final.log: desktop web/native boundaries/speech cancel/wait-notice/realmain rate recovery **26PASS**.
- First desktop lease test failed when cancelled disconnect left stale owner; clearing lease before awaiting detach made the handoff test PASS; invalid presentation dictionaries reject1008 without TypeError.
- Other focused evidence: desktop-related60PASS, native+notice7PASS, rate35PASS, rate wrapper/main66PASS (overlap, do not sum); speech148PASS; original desktop-web related99PASS from subagent.
- mypy273source files PASS; Ruff lint PASS;285Python files format PASS; Node syntax checks and shell syntax PASS. Render SDK build PASS. Whole current Python/source tests passed after relevant fixes; native JS additionally validated by actual source-matched launch.
- Source-only23file reverse-patch and byte comparison PASS, preserves earlier uncommitted startup repair baseline. No private-data restore, deployed rollback, real-cloud429 recovery, human voice/native mouse/long soak proof claimed.

## Running state / rollback

Normal configured8000 backend and one native host are left running; isolated8028 backend shut down. Existing private DB/journal preserved, no new schema or Core format, no private history exported. Browser now opens ?view=control#/chat without renderer/speech duplication. Earlier normal-data backup retained privately; do not restore it over newer conversations. source.patch/before/source-digests/rollback.json cover owned files, excluding unrelated firmware/FIX work. Stop/drain this presentation before reversing source; preserve current DB. Recovery can be disabled on next startup with SIRO_RATE_LIMIT_RECOVERY_ENABLED=0; original ordinary web renderer remains usable after native exit. Menu-entry removal and source reversal do not undo any already executed tools.

## Next required steps

1. Owner runs scripts/repair-nvidia-kernel with sudo authentication, confirms nvidia-smi. Then run isolated GPU-only first-segment comparison, real playback/cancel, and original-voice human listening.
2. Owner confirms native chat/drag/transparent-region behavior; test monitor/DPI/focus/fullscreen limits separately.
3. Continue proper editable character rig and verified activity assets. Window hosting is not the whole VPet feature set.

Official references: [GTK input region](https://docs.gtk.org/gdk3/method.Window.input_shape_combine_region.html), [WebKit RGBA](https://webkitgtk.org/reference/webkit2gtk/2.40.5/method.WebView.set_background_color.html), [Ubuntu signed driver installation](https://ubuntu.com/desktop/docs/en/latest/how-to/graphics/install-nvidia-drivers/), [Groq rate limits](https://console.groq.com/docs/rate-limits).
