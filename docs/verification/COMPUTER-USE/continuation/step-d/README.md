# D / Stage5: opt-in exact process names

SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES=0 by default. ON compares complete normalized
names only (case/whitespace/punctuation, one exact executable suffix), never substring,
prefix or window title authorization. Empty/symbol-only names, paths, differing digits
and helper suffixes do not match. Allowed list entries are not changed.

Backend loop/guard/batch and privacy blocklist use the same check. Focus requests carry
an explicit boolean flag through the existing authenticated bridge; native selection
uses pure matching and refuses multiple candidates. Preserve the stem/full-filename
boundary so game.exe.exe cannot accidentally focus game.exe. Native input paths and
HWND/PID/rect fence, gate/default-off and emergency stop are untouched.

Evidence: 19 Python/JS/PowerShell shared vectors; privacy/entry/focus/default-off and
embedded-extension/ambiguity contracts. Full commands and real exit codes in checks.json.
Pixel baselines were remeasured after implementation. One Claude output save failed
because the directory did not exist; rounded progress retained as failed-save evidence,
then mkdir/stdout preservation fixed/tested and a complete20-case report rerun. The
complete report, NOT reconstructed rounded progress, is authoritative.

Full comparison, flags, known regression failures and honest remaining model-quality
limits are in comparison-final.json and the scoped collaboration handoff. No live input.