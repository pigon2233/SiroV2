# COMPUTER-KEEP-GROUNDED-ACT-20261114

Owner: Grok Bot. LOCAL_ONLY / NOT PUSHED. Base: current local main at start of this task
(`e65f2d8026175684a7feb4125832da5d81b1bfcf`, owner's `debug` commit). Main checkout
override continues from prior authorized computer-use work. Do not touch owner UI
commits, computer.env secrets, running services, safety.py, or desktop-win/main.js.

## Problem (read-only evidence, Asia/Taipei 2026-11-14 01:33–01:34)

Bounded real Play-SIRO on STS2 title, backend checkout verified as main, decider
`claude` (claude-haiku-5-5, pixel, `COORD_GRID=1`, `PLAYBOOK=0`). Seven steps:
strategy then six waits, stopped `stuck_waiting` / "too many waits without progress".

Raw traces in `/home/pepepig/.local/share/siro/data/computer-diag-20261111`
(`reply-*-N-N.json`, `error` empty) show the model returned **kind=act click(395,342)**
on 单人模式 every turn, confidence 0.85–0.70, with expect/reason to enter
single-player. The play console showed `(wait)` because `decision_policy` converts
any act whose `uncertainty` field is non-empty into wait ("wait for a clearer
frame; uncertainty set"). The prompt also tells the model to fill `uncertainty`
every turn; Claude wrote peripheral doubts (是否 存档1 有進行中 run、右下角小字)
and still chose to click.

Frames (960×520, image_rect [0,0,1920,1040]) show a fully visible, clickable main
menu: 单人模式 / 多人模式 / 时间线 / 设置 / 百科大全 / 退出. The marked (395,342)
lands on 单人模式. Top-left 存档1 has "点击编辑". Bottom-right status is readable:
「正在加载模组运行。已加载5个模组。」This is a persistent mod-status line, not a
blocking loading overlay; menu labels are not greyed. Inter-frame pixel churn is
title animation, not a scene change. The menu was interactive; the run never sent
a click.

## Fix

New default-OFF flag `SIRO_COMPUTER_KEEP_GROUNDED_ACT=1`. When on, a **complete**
act (click/move with x,y, or other complete action kinds) is kept even if
`uncertainty` is set. Model-chosen waits, incomplete acts, ask/stuck/low-confidence
rules, the safety gate, allowlist, emergency stop, and default-off control are
unchanged. No prompt rewrite (would be an un-flagged behavior change). No loop.py
rewrite; policy lives in `decide.py`.

## Verification (no real input)

- Offline replay of the seven saved raw replies through `parse_decision` +
  `decision_policy`: default 7/7 become wait; flag on 7/7 stay click(395,342).
  No live Claude/Ollama call.
- Simulator mode `uncertain-act`: same peripheral uncertainty on a correct menu
  click. Flag off → `stuck_waiting`, 0 advances. Flag on → menu and full
  synthetic path (4 advances). Device-free; no process/HTTP executor.
- Unit, computer-use regression, ruff, mypy on the touched files. WSL only,
  `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2`.

## Owner next run (not executed here)

Append (done only if this task's env step succeeded; otherwise do it yourself):

```dotenv
# Keep a complete click when the model fills uncertainty about other UI text.
SIRO_COMPUTER_KEEP_GROUNDED_ACT=1
```

Keep the prior bounded Claude-pixel recommendations (VERIFY_DONE, BOUNDED_VERIFY,
VERIFY_DELAYED_PROGRESS, ALLOWED_PROCESSES, STRICT_BACKEND, SCREEN_GUARD, 10 steps /
120 seconds, AUTONOMOUS=0, ENDLESS=0). Normally reload the backend so the new
code and env load (this task does not restart it). Enable control from the tray,
bring the game forward, same Play-SIRO command. Expect the first decision that
returns a grounded 单人模式 click to be **sent**, not converted to wait. Remaining
risk: Windows focus/input/DPI, whether the game accepts the click, and later
scenes; this fix only stops policy from discarding those clicks.
