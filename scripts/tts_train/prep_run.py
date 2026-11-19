"""Run the whole mix data preparation and report progress for SIRO-Monitor.

MeloTTS venv:
    ~/.venvs/melotts/bin/python scripts/tts_train/prep_run.py --out ~/tts-train/data/mix-v3 [--factor 2]

Steps: prepare_mix.py build (resample + metadata) -> MeloTTS preprocess_text.py
(frontend + BERT features, run from ~/tts-train/MeloTTS/melo) -> prepare_mix.py
oversample. Progress goes to ~/tts-train/data/prep_progress.json, the file the
monitor's data-prep view reads:
    {"stage", "done", "total", "errors", "last_error", "started", "updated", "finished", "failed"}
preprocess_text.py prints tqdm "n/total" and "err! <line> <error>"; both are parsed live.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TPE = timezone(timedelta(hours=8))
HERE = Path(__file__).resolve().parent
PROGRESS = Path("~/tts-train/data/prep_progress.json").expanduser()


class Progress:
    def __init__(self) -> None:
        self.state = {"stage": "", "done": 0, "total": 0, "errors": 0, "last_error": None,
                      "started": datetime.now(TPE).isoformat(timespec="seconds"),
                      "updated": "", "finished": False, "failed": None}

    def set(self, **kw) -> None:
        self.state.update(kw, updated=datetime.now(TPE).isoformat(timespec="seconds"))
        PROGRESS.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROGRESS.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PROGRESS)


def run_streaming(cmd: list[str], cwd: Path, log: Path, prog: Progress, stage: str) -> int:
    """Run cmd, copy its output to log, and turn tqdm / err! lines into progress."""
    tq = re.compile(r"(\d+)/(\d+) \[")
    with log.open("a", encoding="utf-8") as f, subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, errors="replace"
    ) as p:
        buf, last = "", 0.0
        assert p.stdout is not None
        while chunk := p.stdout.read(256):
            f.write(chunk)
            buf += chunk
            parts = re.split(r"[\r\n]", buf)
            buf = parts.pop()
            for part in parts:
                if part.startswith("err!"):
                    prog.state["errors"] += 1
                    prog.state["last_error"] = part[:300]
                m = tq.findall(part)
                if m:
                    done, total = (int(x) for x in m[-1])
                    prog.state["done"], prog.state["total"] = done, total
            now = datetime.now().timestamp()
            if now - last > 2:
                prog.set(stage=stage)
                last = now
        return p.wait()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--factor", type=int, default=2)
    ap.add_argument("--val-per-spk", type=int, default=20)
    ap.add_argument("--melo", default="~/tts-train/MeloTTS/melo")
    args = ap.parse_args()
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    log = out / "prep.log"
    prog = Progress()
    py = sys.executable
    try:
        prog.set(stage="1/3 轉檔與整理清單（44.1 kHz）")
        r = subprocess.run([py, str(HERE / "prepare_mix.py"), "build", "--out", str(out)],
                           capture_output=True, text=True)
        log.open("a", encoding="utf-8").write(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError(f"prepare_mix build exit {r.returncode}: {r.stderr.strip()[-200:]}")
        prog.set(stage="2/3 中文前端＋BERT 特徵", done=0, total=0)
        rc = run_streaming(
            [py, "preprocess_text.py", "--metadata", str(out / "metadata.list"),
             "--val-per-spk", str(args.val_per_spk), "--max-val-total", str(args.val_per_spk * 2)],
            Path(args.melo).expanduser(), log, prog, "2/3 中文前端＋BERT 特徵",
        )
        if rc:
            raise RuntimeError(f"preprocess_text exit {rc}")
        prog.set(stage="3/3 SIRO 過取樣")
        r = subprocess.run([py, str(HERE / "prepare_mix.py"), "oversample", "--out", str(out),
                            "--factor", str(args.factor)], capture_output=True, text=True)
        log.open("a", encoding="utf-8").write(r.stdout + r.stderr)
        if r.returncode:
            raise RuntimeError(f"oversample exit {r.returncode}")
        prog.set(stage="完成", finished=True)
        return 0
    except Exception as exc:  # noqa: BLE001 - report every failure to the monitor
        prog.set(failed=str(exc)[:300])
        return 1


if __name__ == "__main__":
    sys.exit(main())
