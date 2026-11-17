"""Download MeloTTS pretrained weights and check they fit our training config.

Run with the MeloTTS venv from any directory:
    ~/.venvs/melotts/bin/python scripts/tts_train/check_melo_pretrained.py [--config <config.json>]

Fetches (cached by cached_path / HuggingFace, nothing is trained):
  * the generic pretrained G.pth / D.pth / DUR.pth that train.py loads by default
  * the ZH base speaker checkpoint + config (alternative starting point for G)
  * the bert-base-multilingual-uncased model used by the ZH_MIX_EN frontend
Then compares tensor shapes of each checkpoint against a SynthesizerTrn built
from the config, and prints the keys that would not load.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def build_generator(hps):
    from melo.models import SynthesizerTrn

    return SynthesizerTrn(
        len(hps.symbols),
        hps.data.filter_length // 2 + 1,
        hps.train.segment_size // hps.data.hop_length,
        n_speakers=hps.data.n_speakers,
        num_tones=hps.num_tones,
        num_languages=hps.num_languages,
        **hps.model,
    )


def compare(name: str, ckpt_path: str, model) -> None:
    import torch

    state = torch.load(ckpt_path, map_location="cpu")
    weights = state.get("model", state)
    own = model.state_dict()
    mismatch = [(k, tuple(v.shape), tuple(own[k].shape)) for k, v in weights.items()
                if k in own and own[k].shape != v.shape]
    missing = [k for k in own if k not in weights]
    size = os.path.getsize(ckpt_path) / 2**20
    print(f"{name}: {ckpt_path} ({size:.0f} MB) iteration={state.get('iteration')}")
    print(f"   keys={len(weights)} shape_mismatch={len(mismatch)} missing_in_ckpt={len(missing)}")
    for m in mismatch[:8]:
        print("   mismatch", m)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=None,
                    help="training config.json (default: MeloTTS configs/config.json + symbols)")
    args = ap.parse_args()

    from cached_path import cached_path

    import melo
    from melo import utils
    from melo.download_utils import DOWNLOAD_CKPT_URLS, DOWNLOAD_CONFIG_URLS, load_pretrain_model
    from melo.models import MultiPeriodDiscriminator
    from melo.text.symbols import num_languages, num_tones, symbols

    g_path, d_path, dur_path = load_pretrain_model()
    zh_ckpt = str(cached_path(DOWNLOAD_CKPT_URLS["ZH"]))
    zh_cfg = str(cached_path(DOWNLOAD_CONFIG_URLS["ZH"]))

    from transformers import AutoModelForMaskedLM, AutoTokenizer

    AutoTokenizer.from_pretrained("bert-base-multilingual-uncased")
    AutoModelForMaskedLM.from_pretrained("bert-base-multilingual-uncased")
    print("bert-base-multilingual-uncased: ok")

    if args.config:
        hps = utils.get_hparams_from_file(str(args.config.expanduser()))
    else:
        base = Path(melo.__file__).parent / "configs" / "config.json"
        cfg = json.loads(base.read_text(encoding="utf-8"))
        cfg.update(symbols=symbols, num_languages=num_languages, num_tones=num_tones)
        tmp = Path("/tmp/melo_check_config.json")
        tmp.write_text(json.dumps(cfg), encoding="utf-8")
        hps = utils.get_hparams_from_file(str(tmp))
    print(f"config: symbols={len(hps.symbols)} n_speakers={hps.data.n_speakers} sr={hps.data.sampling_rate}")

    zh = json.loads(Path(zh_cfg).read_text(encoding="utf-8"))
    print(f"ZH base config: sr={zh['data']['sampling_rate']} n_speakers={zh['data']['n_speakers']} "
          f"symbols={len(zh['symbols'])} spk2id={zh['data']['spk2id']}")

    net_g = build_generator(hps)
    compare("pretrained G", g_path, net_g)
    compare("ZH base G", zh_ckpt, net_g)
    compare("pretrained D", d_path, MultiPeriodDiscriminator(hps.model.use_spectral_norm))
    print(f"pretrained DUR: {dur_path} ({os.path.getsize(dur_path) / 2**20:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
