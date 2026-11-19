"""Remap MeloTTS's official ZH generator onto our training config's tables.

The HuggingFace ZH model (myshell-ai/MeloTTS-Chinese) was trained with a
112-symbol / 11-tone / 4-language / 256-speaker table, while preprocess_text.py
writes configs with the full 219 / 16 / 8 table and one speaker. Loading it
directly would leave the phone, tone and language embeddings randomly
initialised. This copies rows by symbol name (tones and languages share the
same numbering for the first 11 / 4 ids) and seeds our speaker with the ZH
speaker embedding.

    ~/.venvs/melotts/bin/python scripts/tts_train/convert_zh_checkpoint.py \
        --config ~/tts-train/data/siro-sweet-b-v1/config.json \
        --out ~/tts-train/pretrained/zh-remapped/G_0.pth

Pass the output to train.py with --pretrain_G. No training happens here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import torch
    from huggingface_hub import hf_hub_download
    from melo import utils
    from melo.models import SynthesizerTrn

    zh_ckpt = hf_hub_download("myshell-ai/MeloTTS-Chinese", "checkpoint.pth")
    zh_cfg = json.loads(
        Path(hf_hub_download("myshell-ai/MeloTTS-Chinese", "config.json")).read_text(
            encoding="utf-8"
        )
    )
    src = torch.load(zh_ckpt, map_location="cpu")["model"]

    hps = utils.get_hparams_from_file(str(args.config.expanduser()))
    net_g = SynthesizerTrn(
        len(hps.symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        num_tones=hps.num_tones,
        num_languages=hps.num_languages,
        **hps.model,
    )
    dst = net_g.state_dict()

    ours = {s: i for i, s in enumerate(hps.symbols)}
    emb = dst["enc_p.emb.weight"].clone()
    for zi, sym in enumerate(zh_cfg["symbols"]):
        emb[ours[sym]] = src["enc_p.emb.weight"][zi]
    src["enc_p.emb.weight"] = emb

    for key in ("enc_p.tone_emb.weight", "enc_p.language_emb.weight"):
        table = dst[key].clone()
        table[: src[key].shape[0]] = src[key]
        src[key] = table

    zh_sid = zh_cfg["data"]["spk2id"]["ZH"]
    spk = dst["emb_g.weight"].clone()
    spk[:] = src["emb_g.weight"][zh_sid]
    src["emb_g.weight"] = spk

    bad = [k for k, v in dst.items() if k not in src or src[k].shape != v.shape]
    if bad:
        print("still mismatched:", bad)
        return 1
    args.out.expanduser().parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {"model": src, "iteration": 0, "learning_rate": hps.train.learning_rate, "optimizer": None},
        args.out.expanduser(),
    )
    print(
        f"wrote {args.out} keys={len(src)} (symbols {len(zh_cfg['symbols'])}->{len(hps.symbols)}, "
        f"speaker seeded from ZH id {zh_sid})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
