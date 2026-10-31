# COMPUTER-STS2-TRIAL-20261101

- Owner: Cursor agent, local session; 2026-11-01 Asia/Taipei.
- Status: PARTIAL; LOCAL_ONLY / NOT PUSHED. Control path proven on STS2; owner next wants continuous autonomous play + learning.
- Goal: switch computer-use allowlist from Undertale-only to Slay the Spire 2 (slow-paced), then run a bounded live trial if services are ready.
- Owned paths: this handoff; owner machine config `%USERPROFILE%\siro-computer\computer.env` (ALLOWED_PROCESSES only). No game save edits. No Reset-equivalent destructive actions.
- Exclusions: shared STATUS/DECISIONS, Undertale Logo injection deep-dive (deferred), dirty design/ blender files in main checkout.
- Acceptance: document process name, updated allowlist, whether control/tray/gateway were ready, and any live run result or blockers.
- Coordination: main checkout has unrelated dirty design files; left untouched. No GitHub claim (local-only trial).

## Done so far

- Process name confirmed: `SlayTheSpire2.exe` under `C:\Program Files (x86)\Steam\steamapps\common\Slay the Spire 2\`.
- Updated `%USERPROFILE%\siro-computer\computer.env` allowlist to `slaythespire2.exe,undertale.exe` (cloud screen still 1). Token not printed or committed.
- Restarted SIRO (Stop pet + `siro-stop`, then `scripts/start-win-backend` + desktop-win Electron). Gateway `/health/ready` healthy; pet window `SIRO · 對話` present.
- Launched / focused `SlayTheSpire2` (window title `Slay the Spire 2`).
- Could not complete tray 「電腦操控：開啟」 from automated desktop clicks (hidden tray / IME hit). Auto-review also blocks agent reads of `computer.env` token for `/v1/computer/run`, so the live play POST needs owner approval or owner-run `Play-SIRO.cmd`.

## Owner next (1–2 minutes)

1. Taskbar hidden icons → right-click SIRO tray → 「電腦操控：關閉（點此開啟）」.
2. Put Slay the Spire 2 on the primary screen, windowed if possible, click it to the front.
3. Run: `Play-SIRO.cmd "只打到第一場戰鬥開打為止；不要放棄、不要改設定；不確定就停下問我" 15`
4. Emergency stop: `Ctrl+Alt+Shift+Esc`.

Undertale Logo injection remains deferred; keep `undertale.exe` on the allowlist for a later manual-Z check.

## First live attempt (2026-11-01 ~01:39–01:40 Asia/Taipei)

- Owner asked via chat; local model called `computer.play` with an STS2-bounded goal; tool returned `started=true`.
- Desktop poll took one observe (`/poll` 200 then `/result` 200 within ~2s) and stopped. No Claude vision step ran (too fast for a model call).
- `/v1/computer/status` report: `state=stopped`, `reason=window_not_allowed`, `steps=[]`, control still enabled, executor online.
- Conclusion: failure is foreground process not on allowlist at observe time (likely chat/Cursor focused), not Claude Code quota exhaustion. Retry with STS2 focused on primary screen before start; prefer `Play-SIRO.cmd` delay so the game can be clicked forward.

## Second attempt notes (2026-11-01 ~01:44–01:50)

- Later chat turns pasted `Play-SIRO.cmd ...` into SIRO; those agent runs completed with **no tool calls**, so no new computer loop started. Status still showed the first `window_not_allowed`.
- Agent-started API runs (with STS2 already launched) then failed as `window_not_visible` with empty steps. Foreground was `Grok Bot` on the secondary monitor (`rect` mostly X<0); primary-display crop width became 7px (<32), which maps to `window_not_visible` in `desktop-win/computer-perception.js`.
- Extra bug: goal text `Slay the Spire 2` does **not** match allowlist stem `slaythespire2`, so with two allowlisted games `_focus_target` returns `None` and cannot auto-raise the game. Putting `slaythespire2` in the goal fixes naming; Windows still often denies programmatic focus while Grok/Cursor hold it.
- Not Claude quota. Need the owner to physically click STS2 on the primary screen, keep Grok Bot from staying foreground, then start `Play-SIRO.cmd` (or an API run) immediately.

## Live STS2 proof (2026-11-01 ~02:00–02:12)

- `.\Play-SIRO.cmd` works from PowerShell with `.\` prefix.
- Successful multi-step: mode select → Ironclad → entered a run (`done` with HUD/dialogue evidence).
- Later continue-run stopped at first decision with `low_confidence` and empty steps (model uncertain on dialogue/map; safety stop).
- Owner direction after proof: keep inferring choices, play continuously, and keep learning to improve — not just one-shot goals.

## Proposed next product slices (not started)

1. Long STS2 session: raise bounded limits, soften low_confidence into wait/ask-once/best-effort policy for turn-based only, auto-requeue next goal after stop reasons that are recoverable.
2. Stronger playbook loop: record more structured outcomes (what click changed), prefer notes that mention successful coords/screens.
3. Optional `SIRO_COMPUTER_RECORD=1` demos for future local policy training (C4); owner previously forbade recording their own play.
