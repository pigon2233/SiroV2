# A: generic visual regions / hybrid numbered selection

PARTIAL quality target / LOCAL_ONLY / no live input. Same Stage2 manifest SHA
914077f0196b22cb93dc08413668656f478e7066c097a683c740ec46c350a00a:
20 manually labeled tasks, only 5 unique saved STS2 frames (15 text / 5 icon-only).
Not held out; iterative development on this set risks overfitting. No successful gameplay
sequence or new independent scene is claimed. Frozen images remain private/gitignored.

Final implementation: OCR-first; explicit zero -> generic Pillow contour/color boxes
with original IDs overlaid; explicit-corner positional pruning; optional pixel fallback
requires another flag and explicit zero. Malformed replies fail closed. Gallery is a
separate experiment/default off. Candidate-center coverage is 20/20, NOT model accuracy.
No gold regions, game-specific coordinates or icon templates enter detector/model prompts.

| final backend | all | text | no text | mean sec | median sec |
|---|---:|---:|---:|---:|---:|
| Claude hybrid |17/20|14/15|3/5|4.538949|2.761192|
| gemma4:e4b hybrid GPU24|17/20|13/15|4/5|2.297444|0.702411|

Earlier unchanged pixel and OCR-only results are in Stage2/comparison.json. Hybrid is
better than OCR-only (Claude11/20, Gemma12/20), but final >=18/20 goal is NOT achieved
and Claude pixel20/20 remains more accurate. Do not recommend hybrid as strictly better.
One Claude invalid integer reply counts as a miss; do not silently retry it.
Gemma still confuses End Turn, Defend and map; Claude confuses multiplayer/map and
once returns an invalid ID reply. Frozen OCR latency excluded from all cached mode
numbers, including region work/network/parsing; uncached OCR overhead is in Stage2.
No capture/settle/verification/input latency is included. No Groq key -> not measured.

All iterations are retained, not cherry-picked: v1 full-context Claude18/20, Gemma16/20
(first cold Gemma48.4s included); v2 gallery Gemma15/20; v3 compact merging reduced
center coverage18/20 (Claude17/Gemma14); v4 had a local gallery keyword signature bug
(7/8 failed calls, INVALID for quality comparison), fixed before final full20 rerun.
Loose merging was removed; it incorrectly joined adjacent deck/gear icons.
Final filenames, not the best earlier iteration, define the reported implementation.

Resource mitigation: request num_ctx=8192, draft_num_predict=0, num_gpu=24,
keep_alive=15m. No restart/global service change; timeout90s, fail-fast on resource
failure, no blind inference retries. Flags/default-off described in collaboration doc.
Tests: 91 targeted passed; mypy 5 owned source/test files passed; ruff passed.
No live desktop control validation was performed or authorized by this work.
