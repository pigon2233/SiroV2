"""Score TTS corpus recordings: tone, quality, spectrum, ASR confidence, emotion.

Runs in its own venv (~/.venvs/corpus-scorer: torch cu121, faster-whisper,
funasr, torchmetrics[audio], onnxruntime, librosa, pypinyin, opencc, cn2an).
Set PATH to Linux-only dirs (WSL's Windows ffmpeg cannot run) and add the
venv's nvidia/cublas + nvidia/cudnn lib dirs to LD_LIBRARY_PATH for Whisper
on GPU; ``scripts/tts_train/corpus_scorer.sh`` does both.

Library use (for the regeneration pipeline)::

    scorer = CorpusScorer()
    feats = scorer.features(wav_path, text)       # raw measurements
    scored = rank(list_of_feats)                  # adds per-area badness, suspicion, passed

CLI over an LJSpeech-style corpus (resumable; raw features go to a JSONL)::

    corpus_scorer.sh score --corpus <dir with wavs/ + metadata.csv> --out <quality.csv>

Areas (each 0 = typical, larger = more unusual in the bad direction; robust
z-scores against the scored set, clipped to 0..6):
  音調 tone      pypinyin tone vs. F0 slope per character (Whisper timings),
                 F0 jump rate, F0 range outliers
  音質 quality   DNSMOS (P.835 SIG/BAK/OVRL + P.808), clipping, silence share
  音頻 spectrum  spectral centroid / roll-off outliers, chars per second
  信心 asr       Whisper CER (Trad/Simp + digits folded), Whisper avg_logprob,
                 SenseVoice CER (second opinion)
  情緒 emotion   emotion2vec+ large label/score; expected calm/happy voice, so
                 angry/sad/fearful/disgusted with high confidence counts as bad
Everything is a heuristic. A human listening pass decides; scores only sort.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

CJK = re.compile(r"[一-鿿]")
WHISPER_DIR = "~/.local/share/siro/data/models/faster-whisper-small"
GOOD_EMOTIONS = {"neutral", "happy"}
BAD_EMOTIONS = {"angry", "sad", "fearful", "disgusted"}
AREAS = ["tone", "quality", "spectrum", "asr", "emotion"]
AREA_ZH = {"tone": "音調", "quality": "音質", "spectrum": "音頻", "asr": "信心", "emotion": "情緒"}
# 2026-11-18, owner's 44 marks: ASR CER predicts "bad" best (Whisper AUC 0.79,
# SenseVoice 0.77); tone 0.68, spectrum 0.63, quality 0.58, emotion 0.53 (~chance).
WEIGHTS = {"tone": 0.6, "quality": 0.3, "spectrum": 0.4, "asr": 1.5, "emotion": 0.2}
TEXT_PENALTY = 3.0


# ---------------------------------------------------------------- text helpers
_conv = None


def fold(text: str) -> str:
    """Simplified, lower-case, digits spelled out, only CJK + latin letters."""
    global _conv
    import cn2an
    import opencc

    if _conv is None:
        _conv = opencc.OpenCC("t2s").convert
    text = text.replace(",", "")
    for num in re.findall(r"\d+(?:\.\d+)?", text):
        try:
            text = text.replace(num, cn2an.an2cn(num), 1)
        except Exception:
            pass
    return "".join(re.findall(r"[一-鿿a-z]", _conv(text).lower()))


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)


# ------------------------------------------------------------ acoustic (CPU)
def acoustic(wav: str, words: list) -> dict:
    """F0 / tone / spectrum / level features. Pure CPU, safe in a process pool."""
    import librosa
    from pypinyin import Style, lazy_pinyin

    y, sr = librosa.load(wav, sr=16000)
    hop = 160
    out: dict = {"dur": round(len(y) / sr, 3)}
    raw, sr0 = librosa.load(wav, sr=None)
    out["clip_ratio"] = float(np.mean(np.abs(raw) >= 0.99))
    rms = librosa.feature.rms(y=y, frame_length=400, hop_length=hop)[0]
    db = 20 * np.log10(rms + 1e-9)
    out["silence_ratio"] = float(np.mean(db < db.max() - 40))
    cent = librosa.feature.spectral_centroid(y=raw, sr=sr0)[0]
    roll = librosa.feature.spectral_rolloff(y=raw, sr=sr0, roll_percent=0.95)[0]
    loud = rms[: len(cent)] > np.percentile(rms, 30) if len(rms) >= len(cent) else slice(None)
    out["centroid"] = float(np.median(cent[loud] if isinstance(loud, np.ndarray) else cent))
    out["rolloff95"] = float(np.median(roll[loud] if isinstance(loud, np.ndarray) else roll))

    f0, voiced, _ = librosa.pyin(y, fmin=90, fmax=700, sr=sr, frame_length=1024, hop_length=hop)
    st = 12 * np.log2(np.where(voiced, f0, np.nan) / 100.0)
    v = st[~np.isnan(st)]
    out["voiced_ratio"] = float(np.mean(voiced))
    if len(v) < 10:
        out.update(f0_med=np.nan, f0_range=np.nan, jump_rate=np.nan, tone_mismatch=np.nan, tone_n=0)
        return out
    out["f0_med"] = float(np.median(v))
    out["f0_range"] = float(np.percentile(v, 95) - np.percentile(v, 5))
    d = np.diff(st)
    d = d[~np.isnan(d)]
    out["jump_rate"] = float(np.mean(np.abs(d) > 1.5)) if len(d) else np.nan

    slices = []
    for start, end, text, _p in words:
        chars = CJK.findall(text)
        if chars and end > start:
            step = (end - start) / len(chars)
            slices += [(start + k * step, start + (k + 1) * step, c) for k, c in enumerate(chars)]
    tones = lazy_pinyin(
        "".join(c for *_, c in slices), style=Style.TONE3, neutral_tone_with_five=True
    )
    med, bad, n = out["f0_med"], 0, 0
    for (a, b, _c), py in zip(slices, tones, strict=False):
        if not py or not py[-1].isdigit() or py[-1] == "5":
            continue
        seg = st[int(a * 100) : max(int(a * 100) + 1, int(b * 100))]
        ok = ~np.isnan(seg)
        if ok.sum() < 5:
            continue
        t = np.arange(len(seg)) / 100.0
        slope = float(np.polyfit(t[ok], seg[ok], 1)[0])  # semitones / s
        level = float(np.nanmean(seg)) - med
        tone = int(py[-1])
        n += 1
        bad += (
            (tone == 2 and slope < -20)
            or (tone == 4 and slope > 20)
            or (tone == 1 and abs(slope) > 45)
            or (tone == 3 and level > 4)
        )
    out["tone_n"] = n
    out["tone_mismatch"] = bad / n if n >= 4 else np.nan
    return out


def _acoustic_job(job):
    key, wav, words = job
    try:
        return key, acoustic(wav, words)
    except Exception as exc:
        return key, {"acoustic_error": repr(exc)[:200]}


# ---------------------------------------------------------- models (GPU)
class CorpusScorer:
    def __init__(self, device: str = "cuda", whisper_dir: str = WHISPER_DIR):
        from faster_whisper import WhisperModel
        from funasr import AutoModel

        self.whisper = WhisperModel(
            os.path.expanduser(whisper_dir),
            device=device,
            compute_type="float16" if device == "cuda" else "int8",
        )
        dev = "cuda:0" if device == "cuda" else "cpu"
        self.sensevoice = AutoModel(
            model="FunAudioLLM/SenseVoiceSmall",
            hub="hf",
            device=dev,
            disable_update=True,
            log_level="ERROR",
        )
        self.emotion = AutoModel(
            model="emotion2vec/emotion2vec_plus_large",
            hub="hf",
            device=dev,
            disable_update=True,
            log_level="ERROR",
        )

    def model_features(self, wav: str, text: str) -> dict:
        import librosa
        import torch
        from torchmetrics.functional.audio.dnsmos import (
            deep_noise_suppression_mean_opinion_score as dnsmos,
        )

        segs, _ = self.whisper.transcribe(
            wav, language="zh", beam_size=5, word_timestamps=True, condition_on_previous_text=False
        )
        segs = list(segs)
        asr = "".join(s.text for s in segs).strip()
        words = [
            [round(w.start, 3), round(w.end, 3), w.word, round(w.probability, 3)]
            for s in segs
            for w in (s.words or [])
        ]
        sv = self.sensevoice.generate(input=wav, language="zh", use_itn=True, disable_pbar=True)[0][
            "text"
        ]
        sv_tags = re.findall(r"<\|([^|]+)\|>", sv)
        sv_text = re.sub(r"<\|[^|]+\|>", "", sv).strip()
        em = self.emotion.generate(
            wav, granularity="utterance", extract_embedding=False, disable_pbar=True
        )[0]
        labels = [lab.split("/")[-1] for lab in em["labels"]]
        top = int(np.argmax(em["scores"]))
        y, _ = librosa.load(wav, sr=16000)
        p808, sig, bak, ovrl = dnsmos(torch.tensor(y), 16000, personalized=False).tolist()
        ref = fold(text)
        return {
            "asr": asr,
            "words": words,
            "whisper_cer": round(cer(ref, fold(asr)), 4),
            "avg_logprob": round(sum(s.avg_logprob for s in segs) / len(segs), 4) if segs else -9.0,
            "no_speech_prob": round(max((s.no_speech_prob for s in segs), default=1.0), 4),
            "sensevoice": sv_text,
            "sensevoice_cer": round(cer(ref, fold(sv_text)), 4),
            "sensevoice_tags": sv_tags,
            "emotion": labels[top],
            "emotion_score": round(float(em["scores"][top]), 4),
            "emotion_scores": {
                lab: round(float(s), 4) for lab, s in zip(labels, em["scores"], strict=False)
            },
            "dnsmos_p808": round(p808, 3),
            "dnsmos_sig": round(sig, 3),
            "dnsmos_bak": round(bak, 3),
            "dnsmos_ovrl": round(ovrl, 3),
            "ref_chars": len(ref),
        }

    def features(self, wav: str, text: str) -> dict:
        f = self.model_features(wav, text)
        f.update(acoustic(wav, f["words"]))
        f["cps"] = f["ref_chars"] / f["dur"] if f.get("dur") else np.nan
        return f


# ------------------------------------------------------------ ranking
def _rz(values, higher_is_bad=True):
    arr = np.array([np.nan if v is None else v for v in values], dtype=float)
    ok = arr[~np.isnan(arr)]
    if not len(ok):
        return np.zeros(len(arr))
    med = np.median(ok)
    mad = np.median(np.abs(ok - med)) * 1.4826 or 1e-6
    z = (arr - med) / mad
    z = z if higher_is_bad else -z
    return np.nan_to_num(np.clip(z, 0, 6))


def _abs_rz(values):
    return np.maximum(_rz(values, True), _rz(values, False))


def rank(rows: list[dict], cut_quantile: float = 0.85) -> list[dict]:
    """Add per-area badness, a weighted suspicion score and pass/fail (top 15% fail)."""
    g = lambda k: [r.get(k) for r in rows]  # noqa: E731
    emo_bad = [r.get("emotion_scores", {}) for r in rows]
    emo_bad = [sum(s.get(k, 0) for k in BAD_EMOTIONS) for s in emo_bad]
    area = {
        "tone": (_rz(g("tone_mismatch")) + _rz(g("jump_rate")) + 0.5 * _abs_rz(g("f0_range")))
        / 2.5,
        "quality": (
            _rz(g("dnsmos_ovrl"), False)
            + _rz(g("dnsmos_sig"), False)
            + _rz(g("dnsmos_p808"), False)
            + 2 * _rz(g("clip_ratio"))
            + _rz(g("silence_ratio"))
        )
        / 6,
        "spectrum": (_abs_rz(g("centroid")) + _abs_rz(g("rolloff95")) + _abs_rz(g("cps"))) / 3,
        "asr": (
            1.5 * _rz(g("whisper_cer")) + _rz(g("sensevoice_cer")) + _rz(g("avg_logprob"), False)
        )
        / 3.5,
        # absolute, not a z-score: nearly every clip is "happy", so any small
        # angry/sad probability became a 6-sigma outlier and dominated the ranking
        "emotion": np.clip(6 * np.array(emo_bad, dtype=float), 0, 6),
    }
    total = sum(WEIGHTS[a] * area[a] for a in AREAS)
    cut = float(np.quantile(total, cut_quantile)) if len(total) else 0.0
    # broken source text (check_corpus_text.py): the recording cannot be right
    text_bad = np.array(
        [1.0 if str(r.get("text_issue") or "").strip() not in ("", "nan") else 0.0 for r in rows]
    )
    total = total + TEXT_PENALTY * text_bad
    for i, r in enumerate(rows):
        for a in AREAS:
            r[f"bad_{a}"] = round(float(area[a][i]), 3)
        r["suspicion"] = round(float(total[i]), 3)
        r["passed"] = bool(total[i] <= cut and not text_bad[i])
    order = sorted(range(len(rows)), key=lambda i: -total[i])
    for rank_no, i in enumerate(order, 1):
        rows[i]["rank"] = rank_no
    return rows


CSV_KEYS = [
    "rank",
    "id",
    "passed",
    "owner_mark",
    "suspicion",
    "text_issue",
    *[f"bad_{a}" for a in AREAS],
    "whisper_cer",
    "sensevoice_cer",
    "avg_logprob",
    "no_speech_prob",
    "dnsmos_ovrl",
    "dnsmos_sig",
    "dnsmos_bak",
    "dnsmos_p808",
    "clip_ratio",
    "silence_ratio",
    "centroid",
    "rolloff95",
    "cps",
    "f0_med",
    "f0_range",
    "jump_rate",
    "tone_mismatch",
    "tone_n",
    "voiced_ratio",
    "emotion",
    "emotion_score",
    "dur",
    "text",
    "asr",
    "sensevoice",
    "wav",
]


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_KEYS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["rank"]):
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


# ------------------------------------------------------------------ CLI
def cmd_score(args) -> int:
    corpus = Path(args.corpus).expanduser()
    items = [
        line.split("|", 1)
        for line in (corpus / "metadata.csv").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if args.limit:
        items = items[: args.limit]
    raw_path = Path(args.raw or (str(Path(args.out).expanduser()) + ".raw.jsonl")).expanduser()
    done = {}
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["id"]] = r
    todo = [(u, t) for u, t in items if u not in done]
    print(f"{len(items)} items, {len(done)} already scored, {len(todo)} to go", flush=True)
    if todo:
        scorer = CorpusScorer(device=args.device)
        with raw_path.open("a", encoding="utf-8") as f:
            for n, (u, text) in enumerate(todo, 1):
                wav = str(corpus / "wavs" / f"{u}.wav")
                try:
                    r = {
                        "id": u,
                        "text": text.strip(),
                        "wav": wav,
                        **scorer.model_features(wav, text),
                    }
                except Exception as exc:
                    r = {"id": u, "text": text.strip(), "wav": wav, "model_error": repr(exc)[:200]}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()
                done[u] = r
                if n % 50 == 0:
                    print(f"models {n}/{len(todo)}", flush=True)
    rows = [done[u] for u, _ in items if u in done]
    jobs = [(r["id"], r["wav"], r.get("words", [])) for r in rows]
    with ProcessPoolExecutor(args.workers) as pool:
        for key, feats in pool.map(_acoustic_job, jobs, chunksize=8):
            done[key].update(feats)
    for r in rows:
        r["cps"] = r.get("ref_chars", 0) / r["dur"] if r.get("dur") else np.nan
    rank(rows)
    out = Path(args.out).expanduser()
    write_csv(rows, out)
    print(f"wrote {out}")
    return 0


def cmd_rerank(args) -> int:
    """Recompute area scores / ranking from an existing quality.csv (+ its raw JSONL)."""
    out = Path(args.out).expanduser()
    raw_path = Path(args.raw or (str(out) + ".raw.jsonl")).expanduser()
    raw = {r["id"]: r for r in map(json.loads, raw_path.read_text(encoding="utf-8").splitlines())}
    rows = []
    for r in csv.DictReader(out.open(encoding="utf-8")):
        row = {}
        for k, v in r.items():
            try:
                row[k] = (
                    float(v)
                    if k
                    not in (
                        "id",
                        "text",
                        "asr",
                        "sensevoice",
                        "wav",
                        "emotion",
                        "passed",
                        "text_issue",
                        "owner_mark",
                    )
                    else ("" if v == "nan" else v)
                )
            except ValueError:
                row[k] = np.nan if v in ("", "nan") else v
        row["emotion_scores"] = raw.get(r["id"], {}).get("emotion_scores", {})
        rows.append(row)
    rank(rows)
    # The owner's listening marks always win over the automatic verdict.
    owner: dict[str, str] = {}
    for path in args.marks or []:
        owner.update(
            json.loads(Path(path).expanduser().read_text(encoding="utf-8")).get("marks", {})
        )
    for row in rows:
        mark = owner.get(row["id"], row.get("owner_mark") or "")
        row["owner_mark"] = mark
        if mark in ("ok", "bad"):
            row["passed"] = mark == "ok"
    write_csv(rows, out)
    print(f"reranked {len(rows)} -> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    rr = sub.add_parser("rerank")
    rr.add_argument("--out", required=True)
    rr.add_argument("--raw", default=None)
    rr.add_argument(
        "--marks", nargs="*", help="owner listening-mark JSON files; their ok/bad override passed"
    )
    s = sub.add_parser("score")
    s.add_argument("--corpus", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--raw", default=None)
    s.add_argument("--device", default="cuda")
    s.add_argument("--limit", type=int, default=0)
    # half the cores: 16 pyin workers made the owner's PC sluggish (2026-11-18)
    s.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    args = ap.parse_args()
    return cmd_rerank(args) if args.cmd == "rerank" else cmd_score(args)


if __name__ == "__main__":
    sys.exit(main())
