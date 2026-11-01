# COMPUTER-OBSERVE-VERIFY-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Continues computer-use work on live checkout `E:/coding/股票策略機器學習/SiroV2` + worktree `computer-autonomous-20261101`.
- Goal: fix observe→decide→act→verify loop reliability (not combat strategy quality).
- Owned: `desktop-win/computer-perception.js`, `desktop-win/computer-bridge.test.js`, `src/siro/services/computer_use/{loop,decision,http}.py`, `scripts/computer-play.sh`, related unit tests, this handoff.
- Exclusions: shared STATUS/DECISIONS, Claude auth, game Reset, recording owner play, push/PR.
- Acceptance (ops reliability): reachable map node, resume pause, play card, end turn, leave shop; stuck must not spam clicks/Escape; Ctrl+C calls `/v1/computer/stop`.

## Plan

1. Capture at 1280 width; keep image_size + image_rect for click mapping.
2. Ban only ineffective same-spot clicks; clear after screen change; remove 140px region ban.
3. Outcomes: `sent` then `effective` / `ineffective` after fingerprint check.
4. Unstick: replan once with scene-aware hints; second failure stops with reason (no counter reset loop).
5. Decision JSON: scene/energy/targets/expect/uncertainty; history shows last effective + failures.
6. `computer-play.sh` SIGINT → POST stop.

## Result (PARTIAL)

- Implemented 1–6 above. Region zoom/crop for unread text deferred (uncertainty → `wait` instead of inventing coords).
- Tests: `pytest tests/unit/test_computer_use_loop.py tests/unit/test_computer_use_ollama_decider.py tests/unit/test_computer_use_http.py` → 85 passed; `node --test desktop-win/computer-bridge.test.js` → 12 passed.
- Endless segments no longer auto-continue on scene-stuck reasons (only step/time caps).
- Live gameplay acceptance (map node / pause / card / end turn / leave shop) still needs owner tray run after SIRO+pet restart. LOCAL_ONLY / NOT PUSHED.

## Follow-up: visual vs expect + segment reasons

- Fingerprint change → `visual_change` only; `effective` requires `verify()` confirmed on the new shot; else `unconfirmed`（尚未確認）or `ineffective`.
- Same scene/button without confirmed progress triggers replan / `stuck_no_progress`.
- Status exposes `segment_ends` / `last_segment_end`; Play prints each segment end reason; consecutive identical continue reasons stop after `SIRO_COMPUTER_SAME_SEGMENT_REASON_LIMIT` (default 2).

## Follow-up: pet stays visible + soft decide recovery

- Owner wants SIRO visible during control. `enableControl` no longer hides the pet.
- Capture parks a separate 1×1 always-hidden helper BrowserWindow on the game's display (not the pet).
- `bad_kind` / format / timeout soft-recover inside the segment (`wait` / `(recover)`) instead of burning segments.
- Crop remains game HWND only so a visible pet on another monitor is fine; overlapping the game window can still confuse vision.

## Follow-up: coordinate calibration (in progress)

- Root cause: `physicalBounds` used `bounds * scaleFactor` (wrong secondary origin on mixed DPI) and crop assumed thumbnail == physical pixels.
- Fix: origin via `screen.dipToScreenPoint`; size via this display's scale; crop scaled by `thumbSize/physical`.
- Optional residual affine: `SIRO_COMPUTER_COORD_CALIB=ox,oy,sx,sy` → screen `(ox+sx*x, oy+sy*y)` after image→physical map (default identity).
- Restart SIRO + desktop-win after pull; if clicks still drift, set calib from one known miss (e.g. clicked 10px right → `ox=-10`).

## Follow-up: menu click stuck at ~275,500

- Owner note: SIRO was first kept on the **secondary** monitor on purpose to isolate multi-monitor coord bugs; later moved onto the game only to compare. Overlap is therefore not the original root cause.
- Likely layers: (1) local vision guessing a fixed leftish image xy `(275,500)`; (2) DIP/multi-monitor `image_rect` mapping. Live steps now log `img WxH rect=[…] → screen(x,y)` so these can be told apart.
- Guard still in place: if the pet overlaps the game HWND, observe slides her aside (still visible; restore on control stop) so she is not painted into the crop.
- Vision copy gets a coordinate grid + center hint (`SIRO_COMPUTER_COORD_GRID=0` to disable); prompt prefers x≈w/2 for centered menus.
- Rejected approach: forcing left-side menu clicks to image center — scene-specific hacks hide bad grounding and break combat.
- Ineffective same-spot ban radius 80px / last 3 unresolved clicks.
- Decide budget 90s; endless autonomous keeps re-observing on timeout instead of failing the segment.
