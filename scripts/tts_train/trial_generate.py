"""Generate candidate recordings for a trial plan with Qwen3-TTS voice cloning.

Run with SIRO's Qwen venv (read-only use; SIRO itself must be stopped):
    ~/.local/share/siro/data/qwen-tts-venv/bin/python scripts/tts_train/trial_generate.py \
        --plan ~/.local/share/siro/tts-corpus/siro-sweet-b-v2-trial/plan.json \
        --model ~/.local/share/siro/data/models/qwen3-tts-0.6b-base \
        --voice-profile ~/.local/share/siro/data/voices/siro-sweet-b-v1.json \
        --temperature 0.65 --top-k 30

Unlike scripts/qwen_tts_worker.py this has no audio cache (every call is a new
sample, which is the point of drawing several candidates) and it lowers the
sampling temperature / top-k of both the talker and the code predictor (the
product worker uses 0.9 / 50). For each plan item and each variant (Traditional
or Simplified text fed to Qwen) it writes wavs/<sentence>_<variant><k>.wav,
appends to candidates.jsonl and logs a "generated" line to progress.jsonl for the
corpus monitor. Resumable: existing wavs are skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

TPE = timezone(timedelta(hours=8))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--voice-profile", required=True)
    ap.add_argument("--temperature", type=float, default=0.65)
    ap.add_argument("--top-k", type=int, default=30)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    args = ap.parse_args()

    import numpy as np
    import soundfile as sf
    import torch
    from faster_qwen3_tts import FasterQwen3TTS
    from faster_qwen3_tts.predictor_graph import PredictorGraph

    plan_path = Path(args.plan).expanduser()
    out = plan_path.parent
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    profile = json.loads(Path(args.voice_profile).expanduser().read_text(encoding="utf-8"))
    (out / "wavs").mkdir(exist_ok=True)

    fast = FasterQwen3TTS.from_pretrained(
        str(Path(args.model).expanduser()),
        device="cuda",
        dtype=torch.bfloat16,
        attn_implementation="sdpa",
        local_files_only=True,
    )
    base = fast.model if hasattr(fast, "model") else fast.base_model
    talker = base.model.talker
    fast.predictor_graph = PredictorGraph(
        talker.code_predictor,
        talker.code_predictor.model.config,
        base.model.config.talker_config.hidden_size,
        device="cuda",
        dtype=torch.bfloat16,
        do_sample=True,
        top_k=args.top_k,
        temperature=args.temperature,
    )
    fast.warmup(prefill_len=100)
    voice = base.create_voice_clone_prompt(
        ref_audio=profile["reference_wav"], ref_text=profile["reference_text"], x_vector_only_mode=False
    )
    settings = {"temperature": args.temperature, "top_k": args.top_k, "voice": profile.get("voice_id")}
    (out / "settings.json").write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")

    k_per = int(plan["candidates_per_variant"])
    with (out / "candidates.jsonl").open("a", encoding="utf-8") as cand, (out / "progress.jsonl").open(
        "a", encoding="utf-8"
    ) as prog:
        for item in plan["items"]:
            for variant in plan["variants"]:
                text = item[f"text_{variant}"]
                for k in range(k_per):
                    cid = f"{item['sentence']}_{variant}{k}"
                    wav = out / "wavs" / f"{cid}.wav"
                    if wav.exists():
                        continue
                    t0 = time.monotonic()
                    wavs, sr = fast.generate_voice_clone(
                        text=text,
                        language="Chinese",
                        voice_clone_prompt=voice,
                        temperature=args.temperature,
                        top_k=args.top_k,
                        max_new_tokens=args.max_new_tokens,
                    )
                    audio = np.asarray(wavs[0], dtype=np.float32)
                    sf.write(wav, np.clip(audio, -1, 1), sr, subtype="PCM_16")
                    sec = time.monotonic() - t0
                    row = {
                        "id": cid,
                        "sentence": item["sentence"],
                        "variant": variant,
                        "candidate": k,
                        "text": item["text_trad"],
                        "text_fed": text,
                        "reason": item["reason"],
                        "wav": str(wav),
                        "dur": round(len(audio) / sr, 3),
                        "gen_sec": round(sec, 2),
                    }
                    cand.write(json.dumps(row, ensure_ascii=False) + "\n")
                    cand.flush()
                    prog.write(
                        json.dumps(
                            {
                                "time": datetime.now(TPE).isoformat(),
                                "sentence": item["sentence"],
                                "candidate": f"{variant}{k}",
                                "stage": "generated",
                            }
                        )
                        + "\n"
                    )
                    prog.flush()
                    print(f"{cid} {row['dur']:.1f}s audio in {sec:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
