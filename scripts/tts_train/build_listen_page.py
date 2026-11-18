# ruff: noqa: RUF001
"""Build the owner's listening page from a corpus_scorer quality.csv.

Any python3 (stdlib only):
    python3 scripts/tts_train/build_listen_page.py --csv ~/tts-train/data/siro-sweet-b-v1/quality.csv \
        --page-dir /mnt/c/Users/<you>/AppData/Local/siro-corpus [--all]

Picks the 10 most suspicious, ~20 around the pass/fail cut and the 10 least
suspicious (or every row with --all), copies those wavs next to the page and
writes listen.html. Rows that share a ``sentence`` column are candidates for
one sentence; the page then also offers "選這個". The owner's marks are kept
in the browser (localStorage) and can be downloaded/imported as JSON:
    {"version": 1, "marks": {"<clip id>": "ok" | "bad"}, "choice": {"<sentence>": "<clip id>"}}
Later pipeline steps read that JSON; automatic scores only order the list.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import sys
from pathlib import Path

REFS = {"001329": "擁有者：音調怪", "000620": "擁有者：完美", "000001": "擁有者：聽不懂", "000004": "擁有者：聽不懂"}
AREA_ZH = [("bad_tone", "音調"), ("bad_quality", "音質"), ("bad_spectrum", "音頻"), ("bad_asr", "信心"),
           ("bad_emotion", "情緒")]


def pick(rows: list[dict], show_all: bool) -> list[dict]:
    rows = sorted(rows, key=lambda r: int(r["rank"]))
    if show_all:
        return rows
    n = len(rows)
    failed = sum(r["passed"] == "False" for r in rows)
    lo = max(10, failed - 10)
    chosen = rows[:10] + rows[lo: min(n - 10, failed + 10)] + rows[-10:]
    chosen += [r for r in rows if r["id"] in REFS and r not in chosen]
    seen, out = set(), []
    for r in sorted(chosen, key=lambda r: int(r["rank"])):
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def card(r: dict, n_cand: int) -> str:
    bars = "".join(
        f'<span class="chip" title="{zh}：0 為一般，越大越可疑">{zh} '
        f'<b style="--v:{min(float(r[k]), 6) / 6:.2f}">{float(r[k]):.1f}</b></span>' for k, zh in AREA_ZH)
    ref = f'<span class="ref">{html.escape(REFS[r["id"]])}</span>' if r["id"] in REFS else ""
    choose = '<button data-v="pick">選這個</button>' if n_cand > 1 else ""
    verdict = "可能有問題" if r["passed"] == "False" else "看起來正常"
    return (
        f'<div class="row" data-id="{r["id"]}" data-sentence="{html.escape(r.get("sentence") or r["id"])}">'
        f'<div class="meta">#{r["rank"]} · {r["id"]} · 可疑分數 {float(r["suspicion"]):.2f}（{verdict}）{ref}</div>'
        f'<div class="text">{html.escape(r["text"])}</div>'
        f'<div class="asr">Whisper：{html.escape(r["asr"])}　SenseVoice：{html.escape(r.get("sensevoice", ""))}　'
        f'情緒：{html.escape(r.get("emotion", ""))} {float(r.get("emotion_score") or 0):.0%}　'
        f'DNSMOS {float(r.get("dnsmos_ovrl") or 0):.2f}</div>'
        f'<div class="chips">{bars}</div>'
        f'<audio controls preload="none" src="listen/{r["id"]}.wav"></audio>'
        f'<div class="btns"><button data-v="ok">OK</button><button data-v="bad">怪</button>{choose}</div></div>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--title", default="SIRO 語料試聽")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(Path(args.csv).expanduser(), encoding="utf-8")))
    chosen = pick(rows, args.all)
    page_dir = Path(args.page_dir).expanduser()
    audio = page_dir / "listen"
    audio.mkdir(parents=True, exist_ok=True)
    for r in chosen:
        shutil.copyfile(r["wav"], audio / f"{r['id']}.wav")
    per_sentence: dict[str, int] = {}
    for r in chosen:
        key = r.get("sentence") or r["id"]
        per_sentence[key] = per_sentence.get(key, 0) + 1
    cards = "".join(card(r, per_sentence[r.get("sentence") or r["id"]]) for r in chosen)
    failed = sum(r["passed"] == "False" for r in rows)
    page = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(args.title)}</title><style>
:root{{color-scheme:light dark;--bg:#f6f6f4;--fg:#222;--card:#fff;--muted:#6b6b6b;--line:#e3e3e0;--ok:#2e7d32;--bad:#c62828;--pick:#1565c0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1d;--fg:#eee;--card:#26262a;--muted:#a0a0a0;--line:#3a3a40}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,"Microsoft JhengHei",sans-serif}}
main{{max-width:760px;margin:0 auto;padding:0 16px 40px}}
.row{{background:var(--card);border-radius:10px;padding:12px 16px;margin:10px 0;border:2px solid transparent}}
.meta,.asr{{color:var(--muted);font-size:13px}} .text{{font-size:18px;margin:2px 0}} audio{{width:100%;margin:6px 0 2px}}
.ref{{margin-left:8px;color:var(--pick);font-weight:600}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}} .chip{{font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:12px;padding:0 8px}}
.chip b{{color:color-mix(in srgb,var(--bad) calc(var(--v)*100%),var(--muted))}}
button{{font-size:15px;padding:4px 18px;margin:4px 8px 0 0;border-radius:6px;border:1px solid var(--muted);background:none;color:var(--fg);cursor:pointer}}
.row[data-mark=ok]{{border-color:var(--ok)}} .row[data-mark=bad]{{border-color:var(--bad)}}
.row[data-mark=ok] button[data-v=ok]{{background:var(--ok);color:#fff;border-color:var(--ok)}}
.row[data-mark=bad] button[data-v=bad]{{background:var(--bad);color:#fff;border-color:var(--bad)}}
.row[data-picked] button[data-v=pick]{{background:var(--pick);color:#fff;border-color:var(--pick)}}
.bar{{position:sticky;top:0;z-index:1;background:var(--bg);padding:10px 0;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid var(--line)}}
.bar .grow{{flex:1}} h1{{font-size:20px;margin:16px 0 4px}} .help{{color:var(--muted);font-size:14px}}</style></head>
<body><main><h1>{html.escape(args.title)}</h1>
<p class="help">共 {len(rows)} 句，自動打分判定約 {failed} 句（{failed / max(1, len(rows)):.0%}）可能有問題。這頁列出 {len(chosen)} 句：
最上面最可疑、中間在分界附近、最下面最乾淨，另外加上你之前聽過的 4 句。<br>
每句聽完按「OK」或「怪」。標記會自動存在這個瀏覽器；做完請按「下載標記」，之後的流程會讀這個檔決定用哪些句子。
五個小分數：0 是一般，越大越可疑（音調＝聲調／音高、音質＝雜音與失真、音頻＝頻譜與語速、信心＝語音辨識是否聽得懂、情緒＝是否偏生氣／難過）。</p>
<div class="bar"><span id="count"></span><span class="grow"></span>
<button id="dl">下載標記</button><label><button id="imp" type="button">匯入標記</button>
<input id="file" type="file" accept=".json" hidden></label></div>
{cards}
<script>
const KEY = "siro-listen-v1:" + {json.dumps(Path(args.csv).name)};
let state = {{version: 1, marks: {{}}, choice: {{}}}};
try {{ const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s && s.marks) state = s; }} catch (e) {{}}
const save = () => {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} }};
function paint() {{
  document.querySelectorAll(".row").forEach(r => {{
    const m = state.marks[r.dataset.id]; if (m) r.dataset.mark = m; else delete r.dataset.mark;
    if (state.choice[r.dataset.sentence] === r.dataset.id) r.dataset.picked = ""; else delete r.dataset.picked;
  }});
  const n = Object.keys(state.marks).length, bad = Object.values(state.marks).filter(v => v === "bad").length;
  document.getElementById("count").textContent = `已標 ${{n}} / {len(chosen)}（怪 ${{bad}}）`;
}}
document.querySelectorAll(".row button").forEach(b => b.onclick = () => {{
  const row = b.closest(".row"), id = row.dataset.id;
  if (b.dataset.v === "pick") {{ state.choice[row.dataset.sentence] = id; state.marks[id] = "ok"; }}
  else state.marks[id] = state.marks[id] === b.dataset.v ? undefined : b.dataset.v;
  if (state.marks[id] === undefined) delete state.marks[id];
  save(); paint();
}});
document.querySelectorAll("audio").forEach(a => a.onplay = () =>
  document.querySelectorAll("audio").forEach(o => {{ if (o !== a) o.pause(); }}));
document.getElementById("dl").onclick = () => {{
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {{type: "application/json"}}));
  a.download = "siro-listen-marks.json"; a.click();
}};
document.getElementById("imp").onclick = () => document.getElementById("file").click();
document.getElementById("file").onchange = async e => {{
  try {{ const s = JSON.parse(await e.target.files[0].text()); if (s.marks) {{ state = s; save(); paint(); }} }}
  catch (err) {{ alert("讀取失敗：" + err); }}
}};
paint();
</script></main></body></html>"""
    (page_dir / "listen.html").write_text(page, encoding="utf-8")
    print(f"listening page: {page_dir / 'listen.html'} ({len(chosen)} clips of {len(rows)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
