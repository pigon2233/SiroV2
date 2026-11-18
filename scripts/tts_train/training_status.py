# ruff: noqa: RUF001
"""MeloTTS training progress, as text or as a self-refreshing HTML page.

Read-only: looks at train.log / console.log / train_config.json / G_*.pth in
the run folder and at nvidia-smi. Any python3 works (stdlib only).

    python3 scripts/tts_train/training_status.py                 # text
    python3 scripts/tts_train/training_status.py --html OUT.html # page (meta refresh 5 s)
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
LOSS = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d).*\tINFO\t\[([^\]]+)\]\s*$")


def collect(run: str) -> dict:
    s: dict = {"now": datetime.now(TPE), "run": run}
    s["running"] = subprocess.run(["pgrep", "-f", f"[t]rain.py --c {run}/"],
                                  capture_output=True).returncode == 0
    s["stopfile"] = os.path.exists(os.path.join(run, "STOP"))
    rows = []
    try:
        for line in open(os.path.join(run, "train.log"), encoding="utf-8", errors="replace"):
            m = LOSS.search(line)
            if not m:
                continue
            try:
                v = [float(x) for x in m.group(2).split(",")]
            except ValueError:
                continue
            if len(v) >= 8:
                rows.append((datetime.fromisoformat(m.group(1)).replace(tzinfo=TPE), int(v[6]), v))
    except OSError:
        pass
    try:
        epochs = json.load(open(os.path.join(run, "train_config.json")))["train"]["epochs"]
        tail = open(os.path.join(run, "console.log"), errors="replace").read()[-20000:]
        per = re.findall(r"\d+/(\d+) \[", tail)
        s["total"] = epochs * int(per[-1]) if per else None
    except (OSError, ValueError, KeyError):
        s["total"] = None
    if rows:
        s["time"], s["step"], v = rows[-1]
        s["loss"] = {"mel": v[3], "kl": v[5], "dur": v[4], "gen": v[1], "disc": v[0]}
        seg = [rows[-1]]  # latest stretch where the step keeps increasing
        for r in reversed(rows[:-1]):
            if r[1] < seg[0][1] and (seg[0][0] - r[0]).total_seconds() < 3600:
                seg.insert(0, r)
            else:
                break
        seg = seg[-8:]
        if len(seg) >= 2 and seg[-1][1] > seg[0][1]:
            s["sec"] = (seg[-1][0] - seg[0][0]).total_seconds() / (seg[-1][1] - seg[0][1])
            if s["total"] and s["running"]:
                left = max(0, s["total"] - s["step"]) * s["sec"]
                s["eta"], s["left_h"] = s["now"] + timedelta(seconds=left), left / 3600
    ck = sorted(glob.glob(os.path.join(run, "G_*.pth")), key=os.path.getmtime)
    if ck:
        s["ckpt"] = (os.path.basename(ck[-1]), datetime.fromtimestamp(os.path.getmtime(ck[-1]), TPE))
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
        s["gpu"] = [int(x) for x in out.strip().split(", ")[:3]]
    except (OSError, ValueError):
        s["gpu"] = None
    if s["running"]:
        s["state"] = "訓練中"
    elif s.get("total") and s.get("step", 0) >= s["total"] - 50:
        s["state"] = "已完成"
    elif s["stopfile"]:
        s["state"] = "已暫停"
    else:
        s["state"] = "沒有在跑"
    return s


def lines(s: dict) -> list[tuple[str, str]]:
    out = [("狀態", s["state"])]
    if "step" in s:
        total = s.get("total")
        out.append(("步數", f"{s['step']:,} / {total:,}（{s['step'] / total:.1%}）" if total else f"{s['step']:,}"))
        lo = s["loss"]
        out.append(("loss", f"mel {lo['mel']:.2f}　kl {lo['kl']:.2f}　dur {lo['dur']:.2f}　"
                            f"gen {lo['gen']:.2f}　disc {lo['disc']:.2f}（mel 越低越好；起點 26.0）"))
        out.append(("最後紀錄", f"{s['time']:%m/%d %H:%M:%S}"))
    if "sec" in s:
        out.append(("速度", f"約 {s['sec']:.2f} 秒／步"))
    if "eta" in s:
        out.append(("預計完成", f"{s['eta']:%m/%d %H:%M}（台北，約 {s['left_h']:.1f} 小時後）"))
    if "ckpt" in s:
        out.append(("最新存檔", f"{s['ckpt'][0]}（{s['ckpt'][1]:%m/%d %H:%M}）"))
    if s.get("gpu"):
        u, t, p = s["gpu"]
        out.append(("顯卡", f"{u:,} / {t:,} MiB，使用率 {p}%"))
    return out


def render_html(s: dict) -> str:
    pct = min(1.0, s["step"] / s["total"]) if s.get("total") and "step" in s else 0.0
    rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in lines(s))
    color = {"訓練中": "#2e7d32", "已完成": "#1565c0", "已暫停": "#ef6c00"}.get(s["state"], "#c62828")
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIRO 語音訓練</title><style>
:root{{color-scheme:light dark;--bg:#f6f6f4;--fg:#222;--card:#fff;--muted:#777;--bar:#e3e3e0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1d;--fg:#eee;--card:#26262a;--muted:#999;--bar:#3a3a40}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,"Microsoft JhengHei",sans-serif}}
main{{max-width:640px;margin:32px auto;padding:0 16px}}
.card{{background:var(--card);border-radius:12px;padding:20px 24px;box-shadow:0 1px 3px #0002}}
h1{{font-size:20px;margin:0 0 4px}} .state{{color:{color};font-weight:700}}
.bar{{height:14px;background:var(--bar);border-radius:7px;overflow:hidden;margin:16px 0 4px}}
.bar>div{{height:100%;width:{pct * 100:.1f}%;background:{color}}}
.pct{{text-align:right;color:var(--muted);font-size:14px}}
table{{width:100%;border-collapse:collapse;margin-top:8px}} th{{text-align:left;font-weight:500;color:var(--muted);
white-space:nowrap;padding:6px 16px 6px 0;vertical-align:top}} td{{padding:6px 0;word-break:break-all}}
footer{{color:var(--muted);font-size:13px;margin-top:12px}}</style></head><body><main><div class="card">
<h1>SIRO 語音模型訓練　<span class="state">{html.escape(s["state"])}</span></h1>
<div class="bar"><div></div></div><div class="pct">{pct:.1%}</div>
<table>{rows}</table></div>
<footer>最後更新 {s["now"]:%Y-%m-%d %H:%M:%S}（台北）・每 5 秒自動重新整理・關掉網頁不影響訓練</footer>
</main></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=os.path.expanduser("~/tts-train/runs/siro-sweet-b-v1"))
    ap.add_argument("--html", help="write an HTML page here instead of printing text")
    args = ap.parse_args()
    s = collect(args.run)
    if args.html:
        tmp = args.html + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(render_html(s))
        os.replace(tmp, args.html)
    else:
        print(f"SIRO 語音訓練　{s['now']:%Y-%m-%d %H:%M:%S}（台北）")
        for k, v in lines(s):
            print(f"{k}：{v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
