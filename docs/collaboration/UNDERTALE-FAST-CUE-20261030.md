# UNDERTALE-FAST-CUE-20261030

- Owner: Codex, 2026-10-30 Asia/Taipei. PARTIAL; LOCAL_ONLY / NOT PUSHED.
- Base: `f93abe0d4ffc55bef4fcdfa35875a29b7643cffe`; branch `codex/undertale-fast-observation-20261030`; worktree `E:/coding/Worktrees/undertale-fast-observation-20261030`.
- Task: assess whether the installed local vision model can reliably identify a brief title-screen prompt, to guide a faster perception strategy for Undertale. This is an offline feasibility test only, not a controller.
- Owned paths: `scripts/verify_undertale_screen_cue.py`, `tests/unit/test_undertale_fast_cue.py`, `docs/verification/COMPUTER-USE/undertale-fast-{cue,transcript,holdout,stress,overlay,middle}-20261030.json`, and this handoff. No edits to live gateway, desktop shell, game saves or shared status/decisions.
- No capture or recording of owner gameplay. Use synthetic images, bounded local Ollama requests, fixed label ground truth and latency measurements; retain all outputs, errors and failures. Do not send input or use resulting classifier for real gameplay without held-out real-screen validation and safety gates.
- GitHub public open issues and PR 4 checked; no relevant claim. Local main f8004834c4308dcb3d48a4871f7f93d0d1adcf73, dirty unrelated design files preserved. This record is local only, not a shared lock.
- Existing isolated E2E desktop launch was rejected by automatic review; this task does not bypass or retry it.

## Results

- WSL local `gemma4:e4b`, Ollama, think=false, temperature=0, 8192 context, 128 output tokens. Screens were generated with PIL; none came from a game or desktop. Each case was run once. The model and current live Ollama instance may contend with normal SIRO inference.
- Direct yes/no classification: 9/10 on development layouts; a dialogue screen saying `PRESS Z OR ENTER TO CONTINUE` was falsely classified as the title. First request 1.120 s, next 0.322–0.344 s. The output schema guarantees neither perception nor reasoning.
- Transcribing top/bottom then applying an exact two-line deterministic predicate: 10/10 development, 10/10 similarly constructed held-out strings, and 10/10 simple synthetic noise/blur/dim/offset/tiny cases. Typical warm requests were about 0.4 s; these figures exclude screen capture, input, scheduling, and real load. Held-out cases use the same font/rendering and are not independent real game evidence.
- Important counterexamples: in the five overlay cases, the two-line method incorrectly accepted a `SAVE` overlay (4/5). A three-line transcription method fixed that example but omitted `RESET` in a different overlay and incorrectly accepted it (4/5). The exact failure outputs are retained, not excluded. Both variants are unsuitable to authorize automatic game inputs. The current tests cannot determine whether Undertale shows these synthetic layouts.
- `PYTHONPATH=src ~/.venvs/sirov2/bin/python -m pytest -q tests/unit/test_undertale_fast_cue.py`: 8 passed; Ruff check/format passed. These test the deterministic predicate, not model perception. Raw synthetic results, per-case times and errors are in the six JSON files.
- Adjacent regression: `PYTHONPATH=src ~/.venvs/sirov2/bin/python -m pytest -q tests/unit/test_computer_use*.py tests/unit/test_undertale_fast_cue.py`: 159 passed with one Starlette deprecation warning.
- Next: a reliable decision needs direct independent screen/overlay validation, e.g. verified game-local image geometry and a mechanism that rejects occlusion; test on actual game frames without recording owner gameplay. Only then consider a bounded watch/act implementation through the existing permission, emergency-stop and no-unknown-retry gates. No real inputs, game recordings, live configuration or production paths were changed.
