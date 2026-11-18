# ruff: noqa: RUF001
"""Render the corpus-generation progress page (any python3, stdlib only).

The (future) regeneration script appends one JSON line per scored candidate to
``<gen-dir>/progress.jsonl``::

    {"time": "2026-11-18T20:00:00+08:00", "sentence": "000123", "candidate": 2,
     "passed": true, "suspicion": 1.4,
     "areas": {"tone": 0.3, "quality": 0.1, "spectrum": 0.5, "asr": 0.0, "emotion": 0.0}}

and writes ``<gen-dir>/plan.json`` once: {"total_sentences": N, "candidates_per_sentence": K}.
Until those exist the page shows "尚未開始". Read-only on the generation files.

    python3 scripts/tts_train/corpus_monitor.py --gen-dir ~/tts-train/data/siro-regen --html OUT.html
"""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

TPE = timezone(timedelta(hours=8))
AREAS = [
    ("tone", "音調", "#8e24aa"),
    ("quality", "音質", "#1e88e5"),
    ("spectrum", "音頻", "#00897b"),
    ("asr", "信心", "#f4511e"),
    ("emotion", "情緒", "#6d6d6d"),
]


def load(gen_dir: str) -> tuple[dict, list[dict]]:
    plan, rows = {}, []
    try:
        plan = json.load(open(os.path.join(gen_dir, "plan.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        for line in open(os.path.join(gen_dir, "progress.jsonl"), encoding="utf-8"):
            try:
                r = json.loads(line)
                r["_t"] = datetime.fromisoformat(r["time"])
                rows.append(r)
            except (ValueError, KeyError):
                continue
    except OSError:
        pass
    return plan, rows


def gpu() -> str:
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        u, t, p = (int(x) for x in out.strip().split(", ")[:3])
        return f"{u:,} / {t:,} MiB，使用率 {p}%"
    except Exception:
        return "讀不到"


def chart(rows: list[dict]) -> str:
    """Moving average (window 25 candidates) of each area's badness."""
    if len(rows) < 2:
        return '<p class="muted">資料還不夠畫圖。</p>'
    w, h, left, right, top, bottom = 600, 220, 40, 12, 12, 26
    series = {}
    for key, _zh, _c in AREAS:
        vals = [float(r.get("areas", {}).get(key, 0)) for r in rows]
        series[key] = [
            sum(vals[max(0, i - 24) : i + 1]) / len(vals[max(0, i - 24) : i + 1])
            for i in range(len(vals))
        ]
    hi = max(1.0, max(max(v) for v in series.values()))
    n = len(rows)
    px = lambda i: left + i / (n - 1) * (w - left - right)  # noqa: E731
    py = lambda y: top + (hi - y) / hi * (h - top - bottom)  # noqa: E731
    parts = [
        f'<line x1="{left}" x2="{w - right}" y1="{py(hi * k / 4):.1f}" y2="{py(hi * k / 4):.1f}" class="grid"/>'
        f'<text x="{left - 6}" y="{py(hi * k / 4) + 4:.1f}" text-anchor="end">{hi * k / 4:.1f}</text>'
        for k in range(5)
    ]
    parts += [
        f'<text x="{px(int((n - 1) * k / 4)):.1f}" y="{h - 6}" text-anchor="middle">{int((n - 1) * k / 4) + 1}</text>'
        for k in range(5)
    ]
    for key, _zh, color in AREAS:
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series[key]))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
    legend = "".join(
        f'<span><i style="background:{c}"></i>{zh} {series[k][-1]:.2f}</span>' for k, zh, c in AREAS
    )
    return (
        f'<div class="legend">{legend}</div><svg viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="各項分數移動平均">{"".join(parts)}</svg>'
        '<p class="muted">橫軸是第幾個候選；線是最近 25 個候選的平均，越低越好（0 是一般）。</p>'
    )


def render(gen_dir: str) -> str:
    plan, rows = load(gen_dir)
    now = datetime.now(TPE)
    total = int(plan.get("total_sentences") or 0)
    k = int(plan.get("candidates_per_sentence") or 0)
    sentences = {r["sentence"] for r in rows}
    passed = sum(bool(r.get("passed")) for r in rows)
    done_pct = len(sentences) / total if total else 0.0
    info = []
    if not rows:
        state = "尚未開始" if not plan else "準備中"
    else:
        age = (now - rows[-1]["_t"]).total_seconds()
        state = (
            "已完成"
            if total and len(sentences) >= total
            else ("生成中" if age < 300 else "停住了（5 分鐘沒有新資料）")
        )
    info.append(("狀態", state))
    if total:
        info.append(("已生成句數", f"{len(sentences):,} / {total:,}（{done_pct:.1%}）"))
    if k:
        info.append(("每句候選數", str(k)))
    if rows:
        info.append(
            (
                "候選",
                f"共 {len(rows):,}，通過 {passed:,}，淘汰 {len(rows) - passed:,}（通過率 {passed / len(rows):.0%}）",
            )
        )
        avg = "　".join(
            f"{zh} {sum(float(r.get('areas', {}).get(key, 0)) for r in rows) / len(rows):.2f}"
            for key, zh, _ in AREAS
        )
        info.append(("各項平均", avg))
        recent = rows[-50:]
        span = (recent[-1]["_t"] - recent[0]["_t"]).total_seconds()
        if len(recent) > 1 and span > 0:
            per_cand = span / (len(recent) - 1)
            info.append(("速度", f"約 {per_cand:.1f} 秒／候選"))
            if total and k and state == "生成中":
                left = max(0, total * k - len(rows)) * per_cand
                info.append(
                    (
                        "預計完成",
                        f"{now + timedelta(seconds=left):%m/%d %H:%M}（台北，約 {left / 3600:.1f} 小時後）",
                    )
                )
    info.append(("顯卡", gpu()))
    table = "".join(f"<tr><th>{html.escape(a)}</th><td>{html.escape(b)}</td></tr>" for a, b in info)
    color = {"生成中": "#2e7d32", "已完成": "#1565c0"}.get(state, "#ef6c00")
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="5"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SIRO 語料製作</title><style>
:root{{color-scheme:light dark;--bg:#f6f6f4;--fg:#222;--card:#fff;--muted:#6b6b6b;--line:#e3e3e0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1d;--fg:#eee;--card:#26262a;--muted:#a0a0a0;--line:#3a3a40}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,"Microsoft JhengHei",sans-serif}}
main{{max-width:660px;margin:32px auto;padding:0 16px}} .card{{background:var(--card);border-radius:12px;padding:20px 24px;margin-bottom:16px;box-shadow:0 1px 3px #0002}}
h1{{font-size:20px;margin:0 0 4px}} .state{{color:{color};font-weight:700}} .muted{{color:var(--muted);font-size:13px}}
.bar{{height:14px;background:var(--line);border-radius:7px;overflow:hidden;margin:16px 0 4px}} .bar>div{{height:100%;width:{done_pct * 100:.1f}%;background:{color}}}
table{{width:100%;border-collapse:collapse;margin-top:8px}} th{{text-align:left;font-weight:500;color:var(--muted);white-space:nowrap;padding:6px 16px 6px 0;vertical-align:top}}
td{{padding:6px 0}} svg{{width:100%;height:auto;display:block}} svg text{{font-size:11px;fill:var(--muted)}} .grid{{stroke:var(--line)}}
.legend{{font-size:13px;color:var(--muted)}} .legend span{{margin-right:14px;white-space:nowrap}} .legend i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}}
</style></head><body><main><div class="card"><h1>SIRO 語料製作　<span class="state">{html.escape(state)}</span></h1>
<div class="bar"><div></div></div><table>{table}</table></div>
<div class="card"><b>各項分數（音調／音質／音頻／信心／情緒）</b>{chart(rows)}</div>
<p class="muted">最後更新 {now:%Y-%m-%d %H:%M:%S}（台北）・每 5 秒自動重新整理・關掉網頁不影響生成</p></main></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", default=os.path.expanduser("~/tts-train/data/siro-regen"))
    ap.add_argument("--html", required=True)
    args = ap.parse_args()
    tmp = args.html + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(render(os.path.expanduser(args.gen_dir)))
    os.replace(tmp, args.html)
    return 0


if __name__ == "__main__":
    sys.exit(main())
