# FIX-006 completion allocation probe

2026-10-10, synthetic current composition, configured openai/gpt-oss-20b. Eight sequential requests maximum, unchanged512 completion ceiling/model/messages/stream; B only adds reasoning_effort=low. No executor, retry, production change, private conversation or hidden reasoning artifact. Existing production completion fence remains. Evidence-only bounded SSE consumer reaches DONE/usage without exposing truncated output to product.

[Groq API reference](https://console.groq.com/docs/api-reference) verifies omitted GPT-OSS effort defaults medium, onlylow/medium/high supported; max_tokens deprecated generated completion ceiling. [Reasoning docs](https://console.groq.com/docs/reasoning) distinguish include_reasoning from effort; none/reasoning_format are not GPT-OSS switches. [Official usage type](https://github.com/groq/groq-python/blob/main/src/groq/types/completion_usage.py) defines optional reasoning breakdown of completion; [chunk type](https://github.com/groq/groq-python/blob/main/src/groq/types/chat/chat_completion_chunk.py) allows usage/x_groq.usage. Numeric latest totals only, not cumulative addition; missing isUNKNOWN.

| Case/sample | Effort | Termination | Completion tokens | Reasoning tokens | Non-reasoning tokens | Visible chars |
|---|---|---|---|---|---|---|
| own_failure / 0 | omitted_default | length | 512 | 417 | 95 | 119 |
| own_failure / 0 | low | stop | 207 | 11 | 196 | 225 |
| voice_correction / 0 | omitted_default | stop | 419 | 116 | 303 | 376 |
| voice_correction / 0 | low | length | 512 | 23 | 489 | 636 |
| voice_correction / 1 | omitted_default | length | 512 | 318 | 194 | 239 |
| voice_correction / 1 | low | stop | 334 | 39 | 295 | 365 |
| unknown_effect / 0 | omitted_default | stop | 176 | 136 | 40 | 36 |
| unknown_effect / 0 | low | HTTPStatusError | UNKNOWN | UNKNOWN | UNKNOWN | 0 |

Observed causes are mixed. Own-failure default length used417 reasoning tokens; voice default length used318. Voice low still length with only23 reasoning tokens and489 non-reasoning tokens/636visiblechars: reducing thought budget cannot fix verbosity by itself. A second voice pair swapped completion results (default length/low stop); firstpair defaultstop/lowlength. Low's successful own-failure/voice outputs still request generic retry/checklist or promise segmentation/completion without playback observations. Therefore **REJECT changing production effort based on this probe**, no blind budget expansion/model replacement. More composition instructions are not demonstrated as sufficient either.

The final low unknown-effect call actually returned HTTP429, with noautomaticretry. That new measured429 does not identify the earlier unrecorded5HTTPStatusError causes. Unknown-effect default still asks which operation to repeat, not result readback; zero actual repeats executed.

Completion tokens minus reasoning is a non-reasoning count, not exact visible token count. Eight samples are not statistics or a quality benchmark; latency numbers include transport/model time only and are not TTS speed. Overall FIX-006 staysPARTIAL. Next hypothesis must retain exact own goal/status and validated observation continuity rather than blindly grow the generic prompt or relax terminal/resource fences. [Raw numeric/visible-only evidence](completion-usage-ablation.json).
