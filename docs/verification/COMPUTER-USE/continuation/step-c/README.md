# C / Stage4: behavior-preserving boundaries

Loop facade retains DecisionLoop/LoopReport/public helper aliases and dynamic timing
constants. observe.py owns observation/identity/pixel guard; decide.py prompt + policy;
execute.py coordinate validation; verify.py expectation proof; stuck.py no-progress
strategies. interface.py is the ONLY definition of Decision/StepRecord/VerifyResult/
Decider/errors; decision.py explicitly reexports original names. Existing selectable
Ollama/Claude/Groq backends and factory remain compatible. No backend switch or new
runtime behavior is introduced, so no additional feature flag is needed for extraction.

13 extracted pure helpers have identical ASTs to B (extraction.json). All three legacy
provider prompt AST values also unchanged; string wrapping only removes pre-existing
lint warnings. Observation timing options are supplied dynamically by loop facade so
existing SCREEN_MATCH_* monkeypatch behavior survives. New default flags stay OFF.

99 loop/batch contracts passed; full computer regression331 passed /4 SAME known
failures (screen.jpg fixture, transient CLI retry expectation, missing_expect fixture,
history punctuation). No tests weakened/skipped/removed. 3 new facade identity tests.
Ruff owned boundaries and mypy9 files pass. No native input or running service changes.
