# B / Stage3: bounded batches (experimental, OFF)

Enable only with SIRO_COMPUTER_ACTION_BATCH=1 AND a separately selected exact
SIRO_COMPUTER_BATCH_PROCESSES list. Main SIRO_COMPUTER_ALLOWED_PROCESSES still
mandatory. Left clicks only,2-4 distinct known block IDs/centers; scene combat and
stable-location declaration required. This declaration is a model claim, NOT proof.
Batch capability is bound to one exact Decision identity and drained once.

Fresh foreground identity/PID/rect/image dimensions, privacy, original pixel guard,
clock/run deadline, stop-generation and enabled gate are checked for EVERY input.
All actual input still goes through ComputerBridge.act/ControlGate.check; there is
no alternate executor or enable(). Unknown delivery, rate limit or partial failure
halts immediately with no replay. Semantic expectation verification runs once after
final observation; an unchanged/unconfirmed result stops, never silently succeeds.
Cancellation propagates. No real input was executed in development/evaluation.

27 new batch contracts passed (118 including A/Stage2/evaluator). Scoped mypy5 passed.
Offline provider probe is ONE two-target localization request, derived from existing
Defend+EndTurn labels, NOT a verified successful gameplay sequence. Both backends
failed both-target success: Gemma8.960s (3 actions, wrong IDs), Claude8.347s (1/2
correct). This does NOT establish batching quality; keep it OFF for actual play.
No batch speedup or win rate is claimed. Full regression evidence in handoff.
