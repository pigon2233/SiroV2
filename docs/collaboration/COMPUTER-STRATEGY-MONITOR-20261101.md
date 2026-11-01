# COMPUTER-STRATEGY-MONITOR-20261101

- Owner: Cursor agent; 2026-11-01 Asia/Taipei; PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Goal: (1) clarify trajectory visibility vs secondary monitor; (2) strategy + reactive acts; (3) capture the display that contains the game window.
- Owned: `desktop-win/computer-perception.js`, `src/siro/services/computer_use/{decision,loop,http}.py`, `scripts/computer-play.sh`, tests, this handoff.

## Answers for owner

- Decision trajectory text is printed by `Play-SIRO` / `computer-play.sh` in that console, not drawn on the game. Putting the **log window** on a secondary monitor is fine.
- Putting the **game** on a secondary monitor used to break capture (primary-only). Now capture follows the display that contains the window.

## Result

- Live step printing already streams `click… | 看到: …` and `(strategy)` updates.
- Model maintains a short `strategy`; each act should react immediately under that plan; refreshes on scene change / every 8 steps.
- Multi-monitor observe: `displayForWindow` + crop in that display’s pixel space.

## Unstick / repeat-click fix (same day)

- Root cause: history logged **desktop** coords after `image_to_screen`, so the model kept copying large near-duplicate clicks; `(unstick)` only re-prompted.
- Fix: history + ban list stay in **screenshot** pixels; `_checked_action` rejects `repeat_click` near recent spots; autonomous recovery taps `Escape` once to leave shop/overlay; prompt adds shop→Escape rule.
- Tests: `test_repeat_click_is_rejected_and_autonomous_escapes` (+ stuck helpers). LOCAL_ONLY / NOT PUSHED.

## Secondary monitor + weak model (follow-up)

- Yes: `gemma4:e4b` is weak for STS2 UI — vague identical `seen`, shop-bar spam. System bugs made it worse.
- Capture: never fall back to `sources[0]` (primary) when the game is on another display; mismatch → `capture_wrong_display`. `displayForWindow` uses physical bounds / nearest center (mixed DPI).
- Loop: oversized clicks that fit `image_rect` are scaled into screenshot space; unstick immediately sends `Escape` once; tight always-ban radius + wider ban while seen-stuck.
- Pet must be restarted to load `computer-perception.js`. LOCAL_ONLY / NOT PUSHED.
