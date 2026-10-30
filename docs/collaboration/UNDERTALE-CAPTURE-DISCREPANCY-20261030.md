# UNDERTALE-CAPTURE-DISCREPANCY-20261030

- Owner: Codex; branch `codex/undertale-capture-discrepancy-20261030`; base `a4e27e2f1be243b733cc03d7603fd9570efa9cf0`; LOCAL_ONLY / NOT PUSHED.
- Scope and ownership: record the read-only current-game capture discrepancy, user clarification and limits in this task file. No source, shared documents, service, game inputs or save changes.
- Public GitHub open issues/PR #1, #2, #4 concern ESP32; a local claim is not a lock. Main checkout has unrelated dirty files. Check for overlapping claims again before the result is written.
- Acceptance: accurately distinguish one sampled comparison from real Electron capture and actual play; record uncertainties and avoid storing pixels, hashes or game text.

## Evidence and limits

- The owner identified the game as being in a normal in-game scene; this description was supplied after earlier PrintWindow model probes, and is not proof of their exact scene or a specific next input.
- After the owner brought Undertale to the foreground, one read-only comparison captured the foreground window with Win32 PrintWindow flag 2, then captured its rectangular display region with Graphics.CopyFromScreen. It checked foreground handle, process and rectangle around capture, required the rectangle to fit on the primary display, and compared a 40 x 40 grid in memory. A point counted as close when the sum of absolute RGB channel differences was at most 24. 0.243 of 1600 sampled points were close. No pixels, game text, frame hashes or game inputs were stored or sent.
- These captures were sequential, not simultaneous. Animation, an overlay, occlusion, DPI or other capture differences can affect the result. The display crop was not Electron desktopCapturer, no independent image review established which capture represents the intended game, and one sample is not a quantified reliability rate. A second attempt found the game no longer foreground and captured nothing.
- Prior PrintWindow-based model/OCR results and repeated-frame stability show properties of that capture only. They do not validate what the production Electron observer sees, the correct action, or real game progress. No prior result is reclassified as a successful game-control test.
- Next acceptance: once the test-shell rejection is resolved, compare actual Electron capture with independently observed game state, check overlays/DPI and window identity, then stage real input and measure sustained game progress. Do not choose Reset; user allows saving. Earlier automatic review rejected the isolated Electron E2E launch and did not provide a reason. No attempt was made to bypass or retry it.
