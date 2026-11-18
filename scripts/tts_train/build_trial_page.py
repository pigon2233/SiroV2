# ruff: noqa: RUF001
"""Listening page for a regeneration trial (stdlib only).

    python3 scripts/tts_train/build_trial_page.py --trial ~/.local/share/siro/tts-corpus/siro-sweet-b-v2-trial \
        --page-dir /mnt/c/Users/<you>/AppData/Local/siro-corpus

Per sentence: the best Traditional-input and best Simplified-input candidate side
by side (best = lowest Whisper+SenseVoice CER), the other candidates behind a
toggle. The owner picks one candidate ("選這個") or "全部怪". Choices stay in
the browser and download as JSON:
    {"version": 1, "trial": "<dir name>", "choice": {"t001": "t001_simp2" | "none"}}
The page also tallies how many picks came from Traditional vs Simplified input.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import sys
from pathlib import Path

VAR_ZH = {"trad": "繁體輸入", "simp": "簡體輸入"}


def clip(r: dict, best: bool) -> str:
    cer = f"字錯 W {float(r['whisper_cer']):.0%} / S {float(r['sensevoice_cer']):.0%}"
    return (
        f'<div class="clip{" best" if best else ""}" data-id="{r["id"]}">'
        f'<div class="meta">{"★ 本組最佳 · " if best else ""}#{int(r["candidate"]) + 1} · {cer} · '
        f"可疑 {float(r['suspicion']):.1f}</div>"
        f'<audio controls preload="none" src="trial/{r["id"]}.wav"></audio>'
        f'<div class="asr">Whisper：{html.escape(r["asr"])}</div>'
        f'<button class="pick" data-v="{r["id"]}">選這個</button></div>'
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", required=True)
    ap.add_argument("--page-dir", required=True)
    args = ap.parse_args()
    trial = Path(args.trial).expanduser()
    page_dir = Path(args.page_dir).expanduser()
    rows = list(csv.DictReader(open(trial / "trial_quality.csv", encoding="utf-8")))
    plan = json.loads((trial / "plan.json").read_text(encoding="utf-8"))
    audio = page_dir / "trial"
    if audio.exists():
        shutil.rmtree(audio)
    audio.mkdir(parents=True)
    by: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        shutil.copyfile(r["wav"], audio / f"{r['id']}.wav")
        by.setdefault(r["sentence"], {}).setdefault(r["variant"], []).append(r)

    cards = []
    for item in plan["items"]:
        s = item["sentence"]
        cols = []
        for v in plan["variants"]:
            cands = sorted(by.get(s, {}).get(v, []), key=lambda r: r["best_of_variant"] != "True")
            if not cands:
                continue
            first, rest = cands[0], cands[1:]
            more = "".join(clip(r, False) for r in rest)
            cols.append(
                f'<div class="col"><div class="vh">{VAR_ZH[v]}'
                f'<span class="fed">餵給 Qwen：{html.escape(first["text_fed"])}</span></div>'
                f"{clip(first, True)}"
                f"<details><summary>其他 {len(rest)} 個候選</summary>{more}</details></div>"
            )
        cards.append(
            f'<div class="row" data-sentence="{s}"><div class="meta">{s} · {html.escape(item["reason"])}</div>'
            f'<div class="text">{html.escape(item["text_trad"])}</div>'
            f'<div class="cols">{"".join(cols)}</div>'
            f'<button class="none" data-v="none">全部怪</button><span class="status"></span></div>'
        )
    n = len(plan["items"])
    page = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SIRO 重新生成試聽</title><style>
:root{{color-scheme:light dark;--bg:#f6f6f4;--fg:#222;--card:#fff;--muted:#6b6b6b;--line:#e3e3e0;--ok:#2e7d32;--bad:#c62828;--pick:#1565c0}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1b1d;--fg:#eee;--card:#26262a;--muted:#a0a0a0;--line:#3a3a40}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,"Microsoft JhengHei",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:0 16px 40px}} h1{{font-size:20px;margin:16px 0 4px}} .help{{color:var(--muted);font-size:14px}}
.row{{background:var(--card);border-radius:10px;padding:12px 16px;margin:12px 0;border:2px solid transparent}}
.row[data-done=pick]{{border-color:var(--ok)}} .row[data-done=none]{{border-color:var(--bad)}}
.text{{font-size:19px;margin:2px 0 8px}} .meta,.asr,.fed{{color:var(--muted);font-size:12.5px}} .fed{{display:block;font-weight:400}}
.cols{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
.col{{border:1px solid var(--line);border-radius:8px;padding:8px 10px}} .vh{{font-weight:600}}
.clip{{padding:6px 0;border-top:1px dashed var(--line)}} .clip.best{{border-top:none}} audio{{width:100%;margin:4px 0 0}}
button{{font-size:14px;padding:3px 14px;margin:4px 8px 0 0;border-radius:6px;border:1px solid var(--muted);background:none;color:var(--fg);cursor:pointer}}
.clip[data-picked] button.pick{{background:var(--pick);color:#fff;border-color:var(--pick)}}
.row[data-done=none] button.none{{background:var(--bad);color:#fff;border-color:var(--bad)}}
.status{{font-size:13px;color:var(--muted)}} details summary{{cursor:pointer;color:var(--muted);font-size:13px;margin-top:4px}}
.bar{{position:sticky;top:0;z-index:1;background:var(--bg);padding:10px 0;display:flex;flex-wrap:wrap;gap:8px;align-items:center;border-bottom:1px solid var(--line)}}
.bar .grow{{flex:1}}</style></head><body><main>
<h1>SIRO 重新生成試聽（{n} 句）</h1>
<p class="help">新設定（隨機性 0.65、top_k 30）。每句左右兩組：同一句分別用「繁體字」和「簡體字」餵給 Qwen，各生成 3 次；
每組先放字錯率最低的那個（★），其他的點「其他候選」展開。<br>每句請選一個你覺得最好的按「選這個」；全部都不行就按「全部怪」。
選擇會自動存在這個瀏覽器，做完按「下載選擇」。最上面會統計你選的有幾個來自繁體、幾個來自簡體。</p>
<div class="bar"><span id="count"></span><span class="grow"></span><button id="dl">下載選擇</button>
<button id="imp" type="button">匯入</button><input id="file" type="file" accept=".json" hidden></div>
{"".join(cards)}
<script>
const KEY = "siro-trial-v1:" + {json.dumps(trial.name)};
let state = {{version: 1, trial: {json.dumps(trial.name)}, choice: {{}}}};
try {{ const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s && s.choice) state = s; }} catch (e) {{}}
const save = () => {{ try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}} }};
function paint() {{
  let trad = 0, simp = 0, none = 0;
  document.querySelectorAll(".row").forEach(row => {{
    const c = state.choice[row.dataset.sentence];
    row.querySelectorAll(".clip").forEach(el => {{ if (el.dataset.id === c) el.dataset.picked = ""; else delete el.dataset.picked; }});
    if (!c) {{ delete row.dataset.done; row.querySelector(".status").textContent = ""; return; }}
    row.dataset.done = c === "none" ? "none" : "pick";
    if (c === "none") none++; else if (c.includes("_trad")) trad++; else simp++;
    row.querySelector(".status").textContent = c === "none" ? "全部怪" : "已選 " + c;
  }});
  document.getElementById("count").textContent =
    `已決定 ${{trad + simp + none}} / {n}　選繁體 ${{trad}}・選簡體 ${{simp}}・全部怪 ${{none}}`;
}}
document.querySelectorAll("button.pick, button.none").forEach(b => b.onclick = () => {{
  const s = b.closest(".row").dataset.sentence;
  state.choice[s] = state.choice[s] === b.dataset.v ? undefined : b.dataset.v;
  if (state.choice[s] === undefined) delete state.choice[s];
  save(); paint();
}});
document.querySelectorAll("audio").forEach(a => a.onplay = () =>
  document.querySelectorAll("audio").forEach(o => {{ if (o !== a) o.pause(); }}));
document.getElementById("dl").onclick = () => {{
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {{type: "application/json"}}));
  a.download = "siro-trial-choices.json"; a.click();
}};
document.getElementById("imp").onclick = () => document.getElementById("file").click();
document.getElementById("file").onchange = async e => {{
  try {{ const s = JSON.parse(await e.target.files[0].text()); if (s.choice) {{ state = s; save(); paint(); }} }}
  catch (err) {{ alert("讀取失敗：" + err); }}
}};
paint();
</script></main></body></html>"""
    (page_dir / "trial.html").write_text(page, encoding="utf-8")
    print(f"trial page: {page_dir / 'trial.html'} ({len(rows)} clips, {n} sentences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
