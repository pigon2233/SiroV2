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
